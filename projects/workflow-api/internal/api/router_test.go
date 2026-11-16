// Copyright 2025 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package api

import (
	"bytes"
	"comfyui-api-service/comfyui"
	"comfyui-api-service/internal/auth"
	"comfyui-api-service/internal/config"
	_ "comfyui-api-service/internal/docs"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"io"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
)

const testAPIClientID = "api-router-test.apps.googleusercontent.com"

type routerAuthFixture struct {
	httpClient *http.Client
	validToken string
}

type roundTripperFunc func(*http.Request) (*http.Response, error)

func (f roundTripperFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return f(req)
}

func newRouterAuthFixture(t *testing.T) *routerAuthFixture {
	t.Helper()

	rsaKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("rsa.GenerateKey() failed: %v", err)
	}
	jwksBytes, err := json.Marshal(map[string]any{
		"keys": []map[string]string{
			{
				"kty": "RSA",
				"alg": "RS256",
				"use": "sig",
				"kid": "router-kid-1",
				"n":   base64.RawURLEncoding.EncodeToString(rsaKey.PublicKey.N.Bytes()),
				"e":   base64.RawURLEncoding.EncodeToString([]byte{0x01, 0x00, 0x01}),
			},
		},
	})
	if err != nil {
		t.Fatalf("json.Marshal(jwks) failed: %v", err)
	}

	headerJSON, _ := json.Marshal(map[string]string{"alg": "RS256", "typ": "JWT", "kid": "router-kid-1"})
	payloadJSON, _ := json.Marshal(map[string]any{
		"iss":   "https://accounts.google.com",
		"sub":   "router-test-user",
		"aud":   testAPIClientID,
		"exp":   time.Now().Add(10 * time.Minute).Unix(),
		"email": "tester@example.com",
	})
	signingInput := base64.RawURLEncoding.EncodeToString(headerJSON) + "." + base64.RawURLEncoding.EncodeToString(payloadJSON)
	digest := sha256.Sum256([]byte(signingInput))
	sig, err := rsa.SignPKCS1v15(rand.Reader, rsaKey, crypto.SHA256, digest[:])
	if err != nil {
		t.Fatalf("rsa.SignPKCS1v15() failed: %v", err)
	}

	hc := &http.Client{
		Transport: roundTripperFunc(func(req *http.Request) (*http.Response, error) {
			hdr := make(http.Header)
			hdr.Set("Content-Type", "application/json")
			return &http.Response{
				StatusCode: http.StatusOK,
				Body:       io.NopCloser(bytes.NewReader(jwksBytes)),
				Header:     hdr,
			}, nil
		}),
	}

	return &routerAuthFixture{
		httpClient: hc,
		validToken: signingInput + "." + base64.RawURLEncoding.EncodeToString(sig),
	}
}

func TestRouterBlocksAllUnauthenticatedV1Routes(t *testing.T) {
	var backendHits atomic.Int32
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		backendHits.Add(1)
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(backend.Close)

	comfyClient, err := comfyui.NewClient(backend.URL)
	if err != nil {
		t.Fatalf("comfyui.NewClient(%q) failed: %v", backend.URL, err)
	}

	authFix := newRouterAuthFixture(t)
	cfg := &config.Config{
		ComfyUIBaseURL: backend.URL,
		GoogleClientID: testAPIClientID,
		ServerPort:     "8080",
		GinMode:        gin.TestMode,
	}
	router, err := SetupRouterWithOptions(t.Context(), cfg, comfyClient, RouterOptions{
		AuthHTTPClient: authFix.httpClient,
	})
	if err != nil {
		t.Fatalf("SetupRouterWithOptions() failed: %v", err)
	}

	// /health must remain unauthenticated.
	healthReq := httptest.NewRequestWithContext(t.Context(), http.MethodGet, "/health", nil)
	healthRec := httptest.NewRecorder()
	router.ServeHTTP(healthRec, healthReq)
	if healthRec.Code != http.StatusOK {
		t.Fatalf("GET /health status = %d, want %d", healthRec.Code, http.StatusOK)
	}

	routes := []struct {
		name   string
		method string
		target string
		body   string
	}{
		{name: "queue_prompt", method: http.MethodPost, target: "/api/v1/queue_prompt", body: `{"prompt":{"1":{"class_type":"KSampler"}}}`},
		{name: "get_history", method: http.MethodGet, target: "/api/v1/history/prompt-123"},
		{name: "get_image", method: http.MethodGet, target: "/api/v1/image?filename=out.png&type=output"},
		{name: "upload_image", method: http.MethodPost, target: "/api/v1/upload_image"},
	}

	for _, tc := range routes {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequestWithContext(t.Context(), tc.method, tc.target, strings.NewReader(tc.body))
			if tc.body != "" {
				req.Header.Set("Content-Type", "application/json")
			}
			rec := httptest.NewRecorder()
			router.ServeHTTP(rec, req)

			if rec.Code != http.StatusUnauthorized {
				t.Errorf("%s %s without auth status = %d, want %d", tc.method, tc.target, rec.Code, http.StatusUnauthorized)
			}
		})
	}

	if got := backendHits.Load(); got != 0 {
		t.Errorf("unauthenticated requests reached ComfyUI backend %d times, want 0", got)
	}
}

func TestRouterSwaggerGating(t *testing.T) {
	comfyClient, err := comfyui.NewClient("http://127.0.0.1:8188")
	if err != nil {
		t.Fatalf("comfyui.NewClient() failed: %v", err)
	}

	tests := []struct {
		name          string
		enableSwagger bool
		wantStatus    int
	}{
		{name: "disabled_in_release_by_default", enableSwagger: false, wantStatus: http.StatusNotFound},
		{name: "enabled_when_configured", enableSwagger: true, wantStatus: http.StatusOK},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			cfg := &config.Config{
				ComfyUIBaseURL: "http://127.0.0.1:8188",
				GoogleClientID: testAPIClientID,
				ServerPort:     "8080",
				GinMode:        gin.TestMode,
				EnableSwagger:  tc.enableSwagger,
			}
			router, err := SetupRouter(t.Context(), cfg, comfyClient)
			if err != nil {
				t.Fatalf("SetupRouter() failed: %v", err)
			}

			req := httptest.NewRequestWithContext(t.Context(), http.MethodGet, "/swagger/index.html", nil)
			rec := httptest.NewRecorder()
			router.ServeHTTP(rec, req)

			if rec.Code != tc.wantStatus {
				t.Errorf("GET /swagger/index.html (EnableSwagger=%v) status = %d, want %d", tc.enableSwagger, rec.Code, tc.wantStatus)
			}
		})
	}
}

func TestAuthenticatedHandlersEndToEnd(t *testing.T) {
	var lastUploadedFilename atomic.Value
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodPost && r.URL.Path == "/prompt":
			bodyBytes, _ := io.ReadAll(r.Body)
			if strings.Contains(string(bodyBytes), `"trigger_500"`) {
				http.Error(w, "backend boom", http.StatusInternalServerError)
				return
			}
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"prompt_id":"pid-999","number":1}`))

		case r.Method == http.MethodGet && r.URL.Path == "/history/pid-999":
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"pid-999":{"status":{"completed":true}}}`))

		case r.Method == http.MethodGet && r.URL.Path == "/history/empty":
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{}`))

		case r.Method == http.MethodGet && r.URL.Path == "/history/missing":
			http.Error(w, "not found", http.StatusNotFound)

		case r.Method == http.MethodGet && r.URL.Path == "/history/boom":
			http.Error(w, "history failure", http.StatusInternalServerError)

		case r.Method == http.MethodGet && r.URL.Path == "/view":
			switch r.URL.Query().Get("filename") {
			case "missing.png":
				http.Error(w, "not found", http.StatusNotFound)
				return
			case "boom.png":
				http.Error(w, "view failure", http.StatusInternalServerError)
				return
			}
			_, _ = w.Write([]byte("IMAGE_BYTES"))

		case r.Method == http.MethodPost && r.URL.Path == "/upload/image":
			if err := r.ParseMultipartForm(4 << 20); err != nil {
				http.Error(w, err.Error(), http.StatusBadRequest)
				return
			}
			_, hdr, err := r.FormFile("image")
			if err != nil {
				http.Error(w, err.Error(), http.StatusBadRequest)
				return
			}
			if hdr.Filename == "fail_upstream.png" {
				http.Error(w, "upload failure", http.StatusInternalServerError)
				return
			}
			lastUploadedFilename.Store(hdr.Filename)
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(comfyui.UploadImageResponse{
				Name: hdr.Filename,
				Type: r.FormValue("type"),
			})

		default:
			http.Error(w, "unexpected path", http.StatusInternalServerError)
		}
	}))
	t.Cleanup(backend.Close)

	comfyClient, err := comfyui.NewClient(backend.URL)
	if err != nil {
		t.Fatalf("comfyui.NewClient(%q) failed: %v", backend.URL, err)
	}
	authFix := newRouterAuthFixture(t)
	cfg := &config.Config{
		ComfyUIBaseURL: backend.URL,
		GoogleClientID: testAPIClientID,
		ServerPort:     "8080",
		GinMode:        gin.TestMode,
	}
	router, err := SetupRouterWithOptions(t.Context(), cfg, comfyClient, RouterOptions{
		AuthHTTPClient: authFix.httpClient,
	})
	if err != nil {
		t.Fatalf("SetupRouterWithOptions() failed: %v", err)
	}

	httpTests := []struct {
		name            string
		method          string
		target          string
		body            string
		wantStatus      int
		wantContentType string
	}{
		{
			name:            "queue_prompt_ok",
			method:          http.MethodPost,
			target:          "/api/v1/queue_prompt",
			body:            `{"prompt":{"3":{"class_type":"KSampler"}}}`,
			wantStatus:      http.StatusOK,
			wantContentType: "application/json; charset=utf-8",
		},
		{
			name:            "queue_prompt_bad_json",
			method:          http.MethodPost,
			target:          "/api/v1/queue_prompt",
			body:            `{"prompt":`,
			wantStatus:      http.StatusBadRequest,
			wantContentType: "application/json; charset=utf-8",
		},
		{
			name:            "history_ok",
			method:          http.MethodGet,
			target:          "/api/v1/history/pid-999",
			wantStatus:      http.StatusOK,
			wantContentType: "application/json; charset=utf-8",
		},
		{
			name:            "history_empty_returns_404",
			method:          http.MethodGet,
			target:          "/api/v1/history/empty",
			wantStatus:      http.StatusNotFound,
			wantContentType: "application/json; charset=utf-8",
		},
		{
			name:            "history_upstream_404",
			method:          http.MethodGet,
			target:          "/api/v1/history/missing",
			wantStatus:      http.StatusNotFound,
			wantContentType: "application/json; charset=utf-8",
		},
		{
			name:            "image_png_content_type",
			method:          http.MethodGet,
			target:          "/api/v1/image?filename=out.png&type=output",
			wantStatus:      http.StatusOK,
			wantContentType: "image/png",
		},
		{
			name:            "image_jpeg_content_type",
			method:          http.MethodGet,
			target:          "/api/v1/image?filename=out.jpg&type=output",
			wantStatus:      http.StatusOK,
			wantContentType: "image/jpeg",
		},
		{
			name:            "image_webp_content_type",
			method:          http.MethodGet,
			target:          "/api/v1/image?filename=out.webp&type=output",
			wantStatus:      http.StatusOK,
			wantContentType: "image/webp",
		},
		{
			name:            "image_missing_query_params",
			method:          http.MethodGet,
			target:          "/api/v1/image?filename=out.png",
			wantStatus:      http.StatusBadRequest,
			wantContentType: "application/json; charset=utf-8",
		},
		{
			name:            "image_upstream_404",
			method:          http.MethodGet,
			target:          "/api/v1/image?filename=missing.png&type=output",
			wantStatus:      http.StatusNotFound,
			wantContentType: "application/json; charset=utf-8",
		},
		{
			name:            "image_binary_default_content_type",
			method:          http.MethodGet,
			target:          "/api/v1/image?filename=out.bin&type=output",
			wantStatus:      http.StatusOK,
			wantContentType: "application/octet-stream",
		},
		{
			name:            "image_upstream_500",
			method:          http.MethodGet,
			target:          "/api/v1/image?filename=boom.png&type=output",
			wantStatus:      http.StatusInternalServerError,
			wantContentType: "application/json; charset=utf-8",
		},
		{
			name:            "queue_prompt_upstream_500",
			method:          http.MethodPost,
			target:          "/api/v1/queue_prompt",
			body:            `{"prompt":{"1":"trigger_500"}}`,
			wantStatus:      http.StatusInternalServerError,
			wantContentType: "application/json; charset=utf-8",
		},
		{
			name:            "history_upstream_500",
			method:          http.MethodGet,
			target:          "/api/v1/history/boom",
			wantStatus:      http.StatusInternalServerError,
			wantContentType: "application/json; charset=utf-8",
		},
	}

	for _, tc := range httpTests {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequestWithContext(t.Context(), tc.method, tc.target, strings.NewReader(tc.body))
			req.Header.Set("Authorization", "Bearer "+authFix.validToken)
			if tc.body != "" {
				req.Header.Set("Content-Type", "application/json")
			}
			rec := httptest.NewRecorder()
			router.ServeHTTP(rec, req)

			if rec.Code != tc.wantStatus {
				t.Errorf("%s %s status = %d, want %d; body = %s", tc.method, tc.target, rec.Code, tc.wantStatus, rec.Body.String())
			}
			if gotCT := rec.Header().Get("Content-Type"); gotCT != tc.wantContentType {
				t.Errorf("%s %s Content-Type = %q, want %q", tc.method, tc.target, gotCT, tc.wantContentType)
			}
		})
	}

	// Verify multipart UploadImage sanitizes path traversal filenames.
	var formBuf bytes.Buffer
	mw := multipart.NewWriter(&formBuf)
	_ = mw.WriteField("type", "input")
	_ = mw.WriteField("overwrite", "true")
	part, err := mw.CreateFormFile("image", "../../etc/traversal.png")
	if err != nil {
		t.Fatalf("mw.CreateFormFile() failed: %v", err)
	}
	_, _ = part.Write([]byte("PNG_DATA"))
	_ = mw.Close()

	uploadReq := httptest.NewRequestWithContext(t.Context(), http.MethodPost, "/api/v1/upload_image", &formBuf)
	uploadReq.Header.Set("Authorization", "Bearer "+authFix.validToken)
	uploadReq.Header.Set("Content-Type", mw.FormDataContentType())
	uploadRec := httptest.NewRecorder()
	router.ServeHTTP(uploadRec, uploadReq)

	if uploadRec.Code != http.StatusOK {
		t.Fatalf("POST /api/v1/upload_image status = %d, want %d; body = %s", uploadRec.Code, http.StatusOK, uploadRec.Body.String())
	}
	if gotName, _ := lastUploadedFilename.Load().(string); gotName != "traversal.png" {
		t.Errorf("UploadImage forwarded filename = %q, want %q", gotName, "traversal.png")
	}

	// Verify UploadImage validation and upstream error paths.
	uploadErrorCases := []struct {
		name       string
		typeField  string
		withFile   bool
		filename   string
		wantStatus int
	}{
		{name: "missing_type_field", typeField: "", withFile: true, filename: "ok.png", wantStatus: http.StatusBadRequest},
		{name: "missing_image_file", typeField: "input", withFile: false, wantStatus: http.StatusBadRequest},
		{name: "upstream_500_on_upload", typeField: "input", withFile: true, filename: "fail_upstream.png", wantStatus: http.StatusInternalServerError},
	}

	for _, tc := range uploadErrorCases {
		t.Run(tc.name, func(t *testing.T) {
			var b bytes.Buffer
			w := multipart.NewWriter(&b)
			if tc.typeField != "" {
				_ = w.WriteField("type", tc.typeField)
			}
			if tc.withFile {
				p, err := w.CreateFormFile("image", tc.filename)
				if err != nil {
					t.Fatalf("w.CreateFormFile() failed: %v", err)
				}
				_, _ = p.Write([]byte("DATA"))
			}
			_ = w.Close()

			req := httptest.NewRequestWithContext(t.Context(), http.MethodPost, "/api/v1/upload_image", &b)
			req.Header.Set("Authorization", "Bearer "+authFix.validToken)
			req.Header.Set("Content-Type", w.FormDataContentType())
			rec := httptest.NewRecorder()
			router.ServeHTTP(rec, req)

			if rec.Code != tc.wantStatus {
				t.Errorf("POST /api/v1/upload_image (%s) status = %d, want %d", tc.name, rec.Code, tc.wantStatus)
			}
		})
	}

	// Verify sanitizeFilename rejects dot-only names directly.
	for _, bad := range []string{"", ".", "..", "/"} {
		if got := sanitizeFilename(bad); got != "" {
			t.Errorf("sanitizeFilename(%q) = %q, want empty string", bad, got)
		}
	}

	// Verify IAP header constant is wired through router as well.
	if auth.IAPAssertionHeader != "X-Goog-IAP-JWT-Assertion" {
		t.Errorf("auth.IAPAssertionHeader = %q, want %q", auth.IAPAssertionHeader, "X-Goog-IAP-JWT-Assertion")
	}
}
