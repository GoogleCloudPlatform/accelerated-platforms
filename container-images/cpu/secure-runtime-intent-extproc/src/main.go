// Copyright 2026 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Command intent-extproc is an Envoy ExternalProcessor (ext_proc) service for
// Agent Substrate's atenet-egress gateway (--experimental-additional-egress-extproc-service).
//
// It sits on the decrypted HTTPS MITM filter chain after Substrate's hostname
// EgressPolicy and credential injector, enforcing dynamic per-actor L7 intent
// policies (allowed HTTP methods and URL path prefixes) registered by the agent
// harness before each tool call.
package main

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	corev3 "github.com/envoyproxy/go-control-plane/envoy/config/core/v3"
	extprocv3 "github.com/envoyproxy/go-control-plane/envoy/service/ext_proc/v3"
	envoy_type "github.com/envoyproxy/go-control-plane/envoy/type/v3"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/protobuf/types/known/structpb"
)

const actorIdentityAttribute = "filter_state['dev.ate.actor.identity']"

var (
	grpcAddr         = flag.String("grpc-address", ":50051", "gRPC listen address for Envoy ext_proc")
	httpAddr         = flag.String("http-address", ":8080", "HTTP listen address for intent policy control API and /readyz")
	serverBundle     = flag.String("server-cred-bundle", "/run/servicedns.podcert.ate.dev/credential-bundle.pem", "PEM credential bundle (key+chain) from servicedns.podcert.ate.dev/identity")
	clientCAFile     = flag.String("client-ca-file", "/run/podidentity.podcert.ate.dev/trust-bundle.pem", "PEM trust bundle from podidentity.podcert.ate.dev/identity")
	callerSPIFFEID   = flag.String("caller-spiffe-id", "spiffe://cluster.local/ns/ate-system/sa/atenet-egress", "Required client certificate URI SAN for Envoy ext_proc connections")
	defaultActorRule = flag.String("default-intent-json", "", "Optional JSON IntentRule to seed at startup")
)

type ExtProcServer struct {
	extprocv3.UnimplementedExternalProcessorServer
	store *PolicyStore
}

func (s *ExtProcServer) Process(stream extprocv3.ExternalProcessor_ProcessServer) error {
	for {
		req, err := stream.Recv()
		if errors.Is(err, io.EOF) {
			return nil
		}
		if err != nil {
			return err
		}

		var resp *extprocv3.ProcessingResponse
		switch r := req.Request.(type) {
		case *extprocv3.ProcessingRequest_RequestHeaders:
			resp = s.handleRequestHeaders(req.GetAttributes(), r.RequestHeaders)
		default:
			resp = &extprocv3.ProcessingResponse{
				Response: &extprocv3.ProcessingResponse_RequestHeaders{
					RequestHeaders: &extprocv3.HeadersResponse{
						Response: &extprocv3.CommonResponse{},
					},
				},
			}
		}

		if err := stream.Send(resp); err != nil {
			return err
		}
	}
}

func (s *ExtProcServer) handleRequestHeaders(
	attributes map[string]*structpb.Struct,
	reqHeaders *extprocv3.HttpHeaders,
) *extprocv3.ProcessingResponse {
	var method, authority, reqPath string
	hasAuthHeader := false
	isMockAuthHeader := false

	for _, h := range reqHeaders.GetHeaders().GetHeaders() {
		k := strings.ToLower(h.Key)
		val := h.Value
		if val == "" && len(h.RawValue) > 0 {
			val = string(h.RawValue)
		}
		switch k {
		case ":method":
			method = val
		case ":authority", "host":
			if authority == "" {
				authority = val
			}
		case ":path":
			reqPath = val
		case "authorization":
			trimmed := strings.TrimSpace(val)
			if trimmed != "" {
				hasAuthHeader = true
				if strings.Contains(trimmed, "ghp_replace_with_") || strings.Contains(trimmed, "ghp_mock_") {
					isMockAuthHeader = true
				}
			}
		}
	}

	actorIdentity := extractAttribute(attributes, actorIdentityAttribute)
	actorRef := ParseActorRef(actorIdentity)

	allowed, code, reason, intent := s.store.Evaluate(actorIdentity, method, authority, reqPath, hasAuthHeader)
	decision := "ALLOW"
	if !allowed {
		decision = "DENY"
	}

	ev := AuditEvent{
		Timestamp:     time.Now().UTC().Format(time.RFC3339Nano),
		ActorIdentity: actorIdentity,
		ActorRef:      actorRef,
		Intent:        intent,
		Method:        method,
		Authority:     authority,
		Path:          reqPath,
		HasAuthHeader: hasAuthHeader,
		Decision:      decision,
		StatusCode:    code,
		Reason:        reason,
	}
	s.store.RecordAudit(ev)

	slog.Info("egress_intent_decision",
		slog.String("ate.actor.identity", actorIdentity),
		slog.String("ate.actor.ref", actorRef),
		slog.String("intent", intent),
		slog.String("http.method", method),
		slog.String("http.authority", authority),
		slog.String("http.path", reqPath),
		slog.Bool("credential_injected", hasAuthHeader),
		slog.String("decision", decision),
		slog.Int("status_code", code),
		slog.String("reason", reason),
	)

	if !allowed {
		bodyJSON, _ := json.Marshal(map[string]any{
			"error":          "blocked_by_egress_intent_policy",
			"actor":          actorRef,
			"active_intent":  intent,
			"method":         method,
			"authority":      authority,
			"path":           reqPath,
			"reason":         reason,
			"enforced_by":    "atenet-egress/intent-extproc",
			"status_code":    code,
		})
		return &extprocv3.ProcessingResponse{
			Response: &extprocv3.ProcessingResponse_ImmediateResponse{
				ImmediateResponse: &extprocv3.ImmediateResponse{
					Status: &envoy_type.HttpStatus{
						Code: envoy_type.StatusCode_Forbidden,
					},
					Body: bodyJSON,
					Details: "intent_extproc_denied",
					Headers: &extprocv3.HeaderMutation{
						SetHeaders: []*corev3.HeaderValueOption{
							{
								Header: &corev3.HeaderValue{
									Key:      "content-type",
									RawValue: []byte("application/json"),
								},
							},
							{
								Header: &corev3.HeaderValue{
									Key:      "x-ate-intent-decision",
									RawValue: []byte("denied"),
								},
							},
						},
					},
				},
			},
		}
	}

	commonResp := &extprocv3.CommonResponse{}
	if isMockAuthHeader {
		commonResp.HeaderMutation = &extprocv3.HeaderMutation{
			RemoveHeaders: []string{"authorization"},
		}
	}

	return &extprocv3.ProcessingResponse{
		Response: &extprocv3.ProcessingResponse_RequestHeaders{
			RequestHeaders: &extprocv3.HeadersResponse{
				Response: commonResp,
			},
		},
	}
}

func extractAttribute(attributes map[string]*structpb.Struct, key string) string {
	for _, attrs := range attributes {
		if v, ok := attrs.GetFields()[key]; ok {
			return v.GetStringValue()
		}
	}
	return ""
}

func buildTLSServerCreds(serverBundlePath, clientCAPath, expectedSAN string) (credentials.TransportCredentials, error) {
	loadPool := newPoolLoader(clientCAPath)
	if _, err := loadPool(); err != nil {
		return nil, err
	}
	loadCert := newCertLoader(serverBundlePath)
	if _, err := loadCert(nil); err != nil {
		return nil, err
	}

	cfg := &tls.Config{
		GetConfigForClient: func(*tls.ClientHelloInfo) (*tls.Config, error) {
			pool, err := loadPool()
			if err != nil {
				return nil, err
			}
			return &tls.Config{
				MinVersion:     tls.VersionTLS13,
				GetCertificate: loadCert,
				ClientAuth:     tls.RequireAndVerifyClientCert,
				ClientCAs:      pool,
				VerifyConnection: func(state tls.ConnectionState) error {
					if expectedSAN == "" {
						return nil
					}
					if len(state.PeerCertificates) == 0 {
						return fmt.Errorf("missing client certificate")
					}
					leaf := state.PeerCertificates[0]
					for _, u := range leaf.URIs {
						if u.String() == expectedSAN {
							return nil
						}
					}
					return fmt.Errorf("client URI SANs %v do not match %q", leaf.URIs, expectedSAN)
				},
			}, nil
		},
	}
	return credentials.NewTLS(cfg), nil
}

func newControlMux(store *PolicyStore) *http.ServeMux {
	mux := http.NewServeMux()

	mux.HandleFunc("/readyz", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ready"}`))
	})

	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	})

	// GET /v1/policies -> list active rules
	// POST /v1/policies -> register or update an IntentRule
	// DELETE /v1/policies?actor=<atespace>/<name> -> revoke an actor's IntentRule
	mux.HandleFunc("/v1/policies", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.Method {
		case http.MethodGet:
			_ = json.NewEncoder(w).Encode(map[string]any{
				"policies": store.ListRules(),
			})
		case http.MethodPost, http.MethodPut:
			var rule IntentRule
			if err := json.NewDecoder(r.Body).Decode(&rule); err != nil {
				w.WriteHeader(http.StatusBadRequest)
				_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
				return
			}
			if strings.TrimSpace(rule.Actor) == "" {
				w.WriteHeader(http.StatusBadRequest)
				_ = json.NewEncoder(w).Encode(map[string]string{"error": "field 'actor' is required"})
				return
			}
			store.SetRule(rule)
			slog.Info("intent_policy_updated",
				slog.String("actor", rule.Actor),
				slog.String("intent", rule.Intent),
				slog.Any("allowed_hosts", rule.AllowedHosts),
				slog.Any("allowed_methods", rule.AllowedMethods),
				slog.Any("allowed_path_prefixes", rule.AllowedPathPrefix),
			)
			_ = json.NewEncoder(w).Encode(map[string]any{
				"status": "updated",
				"rule":   rule,
			})
		case http.MethodDelete:
			actor := r.URL.Query().Get("actor")
			if actor == "" {
				w.WriteHeader(http.StatusBadRequest)
				_ = json.NewEncoder(w).Encode(map[string]string{"error": "query parameter 'actor' is required"})
				return
			}
			store.DeleteRule(actor)
			slog.Info("intent_policy_revoked", slog.String("actor", actor))
			_ = json.NewEncoder(w).Encode(map[string]any{
				"status": "revoked",
				"actor":  actor,
			})
		default:
			w.WriteHeader(http.StatusMethodNotAllowed)
		}
	})

	// GET /v1/audit -> list recent L7 egress decisions
	mux.HandleFunc("/v1/audit", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		events := store.ListAuditEvents()
		actorFilter := strings.TrimSpace(r.URL.Query().Get("actor"))
		if actorFilter != "" {
			var filtered []AuditEvent
			for _, ev := range events {
				if ev.ActorRef == actorFilter || strings.HasSuffix(ev.ActorRef, "/"+actorFilter) {
					filtered = append(filtered, ev)
				}
			}
			events = filtered
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"events": events,
		})
	})

	return mux
}

func main() {
	flag.Parse()

	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	store := NewPolicyStore(500)
	if *defaultActorRule != "" {
		var seed IntentRule
		if err := json.Unmarshal([]byte(*defaultActorRule), &seed); err != nil {
			slog.Error("invalid --default-intent-json", slog.Any("err", err))
			os.Exit(1)
		}
		store.SetRule(seed)
	}

	creds, err := buildTLSServerCreds(*serverBundle, *clientCAFile, *callerSPIFFEID)
	if err != nil {
		slog.Error("failed to initialize mTLS server credentials", slog.Any("err", err))
		os.Exit(1)
	}

	grpcServer := grpc.NewServer(grpc.Creds(creds))
	extprocv3.RegisterExternalProcessorServer(grpcServer, &ExtProcServer{store: store})

	grpcLis, err := net.Listen("tcp", *grpcAddr)
	if err != nil {
		slog.Error("failed to listen on gRPC address", slog.String("addr", *grpcAddr), slog.Any("err", err))
		os.Exit(1)
	}

	httpServer := &http.Server{
		Addr:              *httpAddr,
		Handler:           newControlMux(store),
		ReadHeaderTimeout: 10 * time.Second,
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	go func() {
		slog.Info("intent-extproc control HTTP server listening", slog.String("addr", *httpAddr))
		if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("control HTTP server failed", slog.Any("err", err))
			os.Exit(1)
		}
	}()

	go func() {
		<-ctx.Done()
		slog.Info("shutting down intent-extproc")
		_ = httpServer.Close()
		grpcServer.GracefulStop()
	}()

	slog.Info("intent-extproc gRPC server listening",
		slog.String("addr", *grpcAddr),
		slog.String("caller_spiffe_id", *callerSPIFFEID),
	)
	if err := grpcServer.Serve(grpcLis); err != nil && !errors.Is(err, grpc.ErrServerStopped) {
		slog.Error("gRPC server exited with error", slog.Any("err", err))
		os.Exit(1)
	}
}
