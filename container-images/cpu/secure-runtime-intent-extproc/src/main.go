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
package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"slices"
	"strings"
	"sync"
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
	grpcAddr       = flag.String("grpc-address", ":50051", "gRPC listen address for Envoy ext_proc")
	httpAddr       = flag.String("http-address", ":8080", "HTTP listen address for intent policy control API")
	serverBundle   = flag.String("server-cred-bundle", "/run/servicedns.podcert.ate.dev/credential-bundle.pem", "PEM credential bundle (key+chain)")
	clientCAFile   = flag.String("client-ca-file", "/run/podidentity.podcert.ate.dev/trust-bundle.pem", "PEM client CA trust bundle")
	callerSPIFFEID = flag.String("caller-spiffe-id", "spiffe://cluster.local/ns/ate-system/sa/atenet-egress", "Required client URI SAN")
)

type IntentRule struct {
	Actor             string   `json:"actor"`
	Intent            string   `json:"intent"`
	AllowedHosts      []string `json:"allowed_hosts"`
	AllowedMethods    []string `json:"allowed_methods"`
	AllowedPathPrefix []string `json:"allowed_path_prefixes"`
	UpdatedAt         string   `json:"updated_at"`
}

type AuditEvent struct {
	Timestamp     string `json:"timestamp"`
	ActorIdentity string `json:"ate.actor.identity"`
	ActorRef      string `json:"ate.actor.ref"`
	Intent        string `json:"intent"`
	Method        string `json:"http.method"`
	Authority     string `json:"http.authority"`
	Path          string `json:"http.path"`
	HasAuthHeader bool   `json:"credential_injected"`
	Decision      string `json:"decision"`
	StatusCode    int    `json:"status_code"`
	Reason        string `json:"reason"`
}

type PolicyStore struct {
	mu        sync.RWMutex
	rules     map[string]IntentRule
	events    []AuditEvent
	maxEvents int
}

func NewPolicyStore(maxEvents int) *PolicyStore {
	return &PolicyStore{rules: make(map[string]IntentRule), maxEvents: max(maxEvents, 200)}
}

func (s *PolicyStore) SetRule(rule IntentRule) {
	s.mu.Lock()
	defer s.mu.Unlock()
	rule.Actor = strings.TrimSpace(rule.Actor)
	for i, m := range rule.AllowedMethods {
		rule.AllowedMethods[i] = strings.ToUpper(strings.TrimSpace(m))
	}
	for i, h := range rule.AllowedHosts {
		rule.AllowedHosts[i] = strings.ToLower(strings.TrimSpace(h))
	}
	rule.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	s.rules[rule.Actor] = rule
}

func (s *PolicyStore) DeleteRule(actor string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.rules, strings.TrimSpace(actor))
}

func (s *PolicyStore) RecordAudit(ev AuditEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.events) >= s.maxEvents {
		s.events = s.events[1:]
	}
	s.events = append(s.events, ev)
}

func (s *PolicyStore) ListAuditEvents() []AuditEvent {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return slices.Clone(s.events)
}

func ParseActorRef(rawIdentity string) string {
	rawIdentity = strings.TrimSpace(rawIdentity)
	if !strings.HasPrefix(rawIdentity, "spiffe://") {
		return rawIdentity
	}
	u, err := url.Parse(rawIdentity)
	if err != nil {
		return rawIdentity
	}
	if seg := strings.Split(strings.TrimPrefix(u.Path, "/"), "/"); len(seg) == 3 && (seg[0] == "worker-for-actor" || seg[0] == "actor") {
		return seg[1] + "/" + seg[2]
	}
	return rawIdentity
}

func (s *PolicyStore) Evaluate(actorIdentity, method, authority, reqPath string, _ bool) (bool, int, string, string) {
	actorRef := ParseActorRef(actorIdentity)
	method = strings.ToUpper(strings.TrimSpace(method))
	host, _, _ := strings.Cut(strings.ToLower(strings.TrimSpace(authority)), ":")
	cleanPath, _, _ := strings.Cut(reqPath, "?")

	s.mu.RLock()
	rule, ok := s.rules[actorRef]
	if !ok {
		if _, bare, hasSlash := strings.Cut(actorRef, "/"); hasSlash {
			rule, ok = s.rules[bare]
		}
	}
	s.mu.RUnlock()
	if !ok {
		return false, 403, fmt.Sprintf("intent-extproc: no active intent policy registered for actor %q (default-deny)", actorRef), "none"
	}
	if len(rule.AllowedHosts) > 0 && !slices.Contains(rule.AllowedHosts, "*") && !slices.Contains(rule.AllowedHosts, host) {
		return false, 403, fmt.Sprintf("intent-extproc: host %q is not permitted by intent %q (allowed hosts: %v)", host, rule.Intent, rule.AllowedHosts), rule.Intent
	}
	if !slices.Contains(rule.AllowedMethods, "*") && !slices.Contains(rule.AllowedMethods, method) {
		return false, 403, fmt.Sprintf("intent-extproc: HTTP method %s to %s%s is blocked by intent %q (allowed methods: %v)", method, host, cleanPath, rule.Intent, rule.AllowedMethods), rule.Intent
	}
	if len(rule.AllowedPathPrefix) > 0 && !slices.ContainsFunc(rule.AllowedPathPrefix, func(p string) bool { return p == "*" || strings.HasPrefix(cleanPath, p) }) {
		return false, 403, fmt.Sprintf("intent-extproc: path %q on %s is outside the scope of intent %q (allowed prefixes: %v)", cleanPath, host, rule.Intent, rule.AllowedPathPrefix), rule.Intent
	}
	return true, 200, fmt.Sprintf("allowed by intent %q", rule.Intent), rule.Intent
}

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
		resp := &extprocv3.ProcessingResponse{
			Response: &extprocv3.ProcessingResponse_RequestHeaders{
				RequestHeaders: &extprocv3.HeadersResponse{Response: &extprocv3.CommonResponse{}},
			},
		}
		if r, ok := req.Request.(*extprocv3.ProcessingRequest_RequestHeaders); ok {
			resp = s.handleRequestHeaders(req.GetAttributes(), r.RequestHeaders)
		}
		if err := stream.Send(resp); err != nil {
			return err
		}
	}
}

func (s *ExtProcServer) handleRequestHeaders(attributes map[string]*structpb.Struct, reqHeaders *extprocv3.HttpHeaders) *extprocv3.ProcessingResponse {
	var method, authority, reqPath, actorIdentity string
	hasAuth := false
	for _, h := range reqHeaders.GetHeaders().GetHeaders() {
		v := h.Value
		if v == "" {
			v = string(h.RawValue)
		}
		switch strings.ToLower(h.Key) {
		case ":method":
			method = v
		case ":authority", "host":
			if authority == "" {
				authority = v
			}
		case ":path":
			reqPath = v
		case "authorization":
			hasAuth = strings.TrimSpace(v) != ""
		}
	}
	for _, attrs := range attributes {
		if v, ok := attrs.GetFields()[actorIdentityAttribute]; ok {
			actorIdentity = v.GetStringValue()
			break
		}
	}
	actorRef := ParseActorRef(actorIdentity)
	allowed, code, reason, intent := s.store.Evaluate(actorIdentity, method, authority, reqPath, hasAuth)
	decision := map[bool]string{true: "ALLOW", false: "DENY"}[allowed]
	s.store.RecordAudit(AuditEvent{
		Timestamp: time.Now().UTC().Format(time.RFC3339Nano), ActorIdentity: actorIdentity,
		ActorRef: actorRef, Intent: intent, Method: method, Authority: authority,
		Path: reqPath, HasAuthHeader: hasAuth, Decision: decision, StatusCode: code, Reason: reason,
	})
	slog.Info("egress_intent_decision", "ate.actor.ref", actorRef, "intent", intent, "http.method", method, "http.authority", authority, "http.path", reqPath, "decision", decision, "status_code", code)
	if !allowed {
		bodyJSON, _ := json.Marshal(map[string]any{
			"error": "blocked_by_egress_intent_policy", "actor": actorRef, "active_intent": intent,
			"method": method, "authority": authority, "path": reqPath, "reason": reason, "status_code": code,
		})
		return &extprocv3.ProcessingResponse{
			Response: &extprocv3.ProcessingResponse_ImmediateResponse{
				ImmediateResponse: &extprocv3.ImmediateResponse{
					Status:  &envoy_type.HttpStatus{Code: envoy_type.StatusCode_Forbidden},
					Body:    bodyJSON,
					Details: "intent_extproc_denied",
					Headers: &extprocv3.HeaderMutation{
						SetHeaders: []*corev3.HeaderValueOption{
							{Header: &corev3.HeaderValue{Key: "content-type", RawValue: []byte("application/json")}},
							{Header: &corev3.HeaderValue{Key: "x-ate-intent-decision", RawValue: []byte("denied")}},
						},
					},
				},
			},
		}
	}
	return &extprocv3.ProcessingResponse{
		Response: &extprocv3.ProcessingResponse_RequestHeaders{
			RequestHeaders: &extprocv3.HeadersResponse{Response: &extprocv3.CommonResponse{}},
		},
	}
}

func buildTLSServerCreds(serverBundlePath, clientCAPath, expectedSAN string) (credentials.TransportCredentials, error) {
	if _, err := tls.LoadX509KeyPair(serverBundlePath, serverBundlePath); err != nil {
		return nil, fmt.Errorf("load server credential bundle %q: %w", serverBundlePath, err)
	}
	if _, err := os.ReadFile(clientCAPath); err != nil {
		return nil, fmt.Errorf("read client trust bundle %q: %w", clientCAPath, err)
	}
	return credentials.NewTLS(&tls.Config{
		GetConfigForClient: func(*tls.ClientHelloInfo) (*tls.Config, error) {
			pemBytes, err := os.ReadFile(clientCAPath)
			if err != nil {
				return nil, err
			}
			pool := x509.NewCertPool()
			if !pool.AppendCertsFromPEM(pemBytes) {
				return nil, fmt.Errorf("no valid certs in %q", clientCAPath)
			}
			return &tls.Config{
				MinVersion: tls.VersionTLS13,
				GetCertificate: func(*tls.ClientHelloInfo) (*tls.Certificate, error) {
					c, err := tls.LoadX509KeyPair(serverBundlePath, serverBundlePath)
					return &c, err
				},
				ClientAuth: tls.RequireAndVerifyClientCert,
				ClientCAs:  pool,
				VerifyConnection: func(state tls.ConnectionState) error {
					if expectedSAN == "" {
						return nil
					}
					for _, cert := range state.PeerCertificates[:min(1, len(state.PeerCertificates))] {
						for _, u := range cert.URIs {
							if u.String() == expectedSAN {
								return nil
							}
						}
					}
					return fmt.Errorf("client certificate missing URI SAN %q", expectedSAN)
				},
			}, nil
		},
	}), nil
}

func newControlMux(store *PolicyStore) *http.ServeMux {
	mux := http.NewServeMux()
	for _, p := range []string{"/readyz", "/healthz"} {
		mux.HandleFunc(p, func(w http.ResponseWriter, _ *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"status":"ok"}`))
		})
	}
	mux.HandleFunc("/v1/policies", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.Method {
		case http.MethodPost, http.MethodPut:
			var rule IntentRule
			if err := json.NewDecoder(r.Body).Decode(&rule); err != nil || strings.TrimSpace(rule.Actor) == "" {
				w.WriteHeader(http.StatusBadRequest)
				return
			}
			store.SetRule(rule)
			_ = json.NewEncoder(w).Encode(map[string]any{"status": "updated", "rule": rule})
		case http.MethodDelete:
			actor := r.URL.Query().Get("actor")
			store.DeleteRule(actor)
			_ = json.NewEncoder(w).Encode(map[string]any{"status": "revoked", "actor": actor})
		default:
			w.WriteHeader(http.StatusMethodNotAllowed)
		}
	})
	mux.HandleFunc("/v1/audit", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		events := store.ListAuditEvents()
		if f := strings.TrimSpace(r.URL.Query().Get("actor")); f != "" {
			events = slices.DeleteFunc(events, func(ev AuditEvent) bool {
				return ev.ActorRef != f && !strings.HasSuffix(ev.ActorRef, "/"+f)
			})
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"events": events})
	})
	return mux
}

func main() {
	flag.Parse()
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))
	store := NewPolicyStore(500)
	creds, err := buildTLSServerCreds(*serverBundle, *clientCAFile, *callerSPIFFEID)
	if err != nil {
		slog.Error("mTLS init failed", "err", err)
		os.Exit(1)
	}
	grpcServer := grpc.NewServer(grpc.Creds(creds))
	extprocv3.RegisterExternalProcessorServer(grpcServer, &ExtProcServer{store: store})
	lis, err := net.Listen("tcp", *grpcAddr)
	if err != nil {
		slog.Error("listen failed", "addr", *grpcAddr, "err", err)
		os.Exit(1)
	}
	httpServer := &http.Server{Addr: *httpAddr, Handler: newControlMux(store), ReadHeaderTimeout: 10 * time.Second}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	go func() { _ = httpServer.ListenAndServe() }()
	go func() { <-ctx.Done(); _ = httpServer.Close(); grpcServer.GracefulStop() }()
	_ = grpcServer.Serve(lis)
}
