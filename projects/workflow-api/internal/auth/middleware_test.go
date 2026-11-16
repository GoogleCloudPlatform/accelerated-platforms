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

package auth

import (
	"bytes"
	"crypto"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"io"
	"log"
	"math/big"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
)

const (
	testOIDCKeyID   = "test-oidc-rsa-kid"
	testIAPKeyID    = "test-iap-ec-kid"
	testClientID    = "workflow-client.apps.googleusercontent.com"
	testIAPAudience = "/projects/123456789/global/backendServices/987654321"
)

type testKeySet struct {
	rsaKey     *rsa.PrivateKey
	ecKey      *ecdsa.PrivateKey
	httpClient *http.Client
}

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return f(req)
}

func newTestKeySet(t *testing.T) *testKeySet {
	t.Helper()

	rsaKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("rsa.GenerateKey() failed: %v", err)
	}
	ecKey, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatalf("ecdsa.GenerateKey() failed: %v", err)
	}

	oidcJWKS, err := json.Marshal(map[string]any{
		"keys": []map[string]string{
			{
				"kty": "RSA",
				"alg": "RS256",
				"use": "sig",
				"kid": testOIDCKeyID,
				"n":   base64.RawURLEncoding.EncodeToString(rsaKey.PublicKey.N.Bytes()),
				"e":   base64.RawURLEncoding.EncodeToString(big.NewInt(int64(rsaKey.PublicKey.E)).Bytes()),
			},
		},
	})
	if err != nil {
		t.Fatalf("json.Marshal(oidcJWKS) failed: %v", err)
	}

	xBytes := make([]byte, 32)
	yBytes := make([]byte, 32)
	ecKey.PublicKey.X.FillBytes(xBytes)
	ecKey.PublicKey.Y.FillBytes(yBytes)
	iapJWKS, err := json.Marshal(map[string]any{
		"keys": []map[string]string{
			{
				"kty": "EC",
				"alg": "ES256",
				"crv": "P-256",
				"use": "sig",
				"kid": testIAPKeyID,
				"x":   base64.RawURLEncoding.EncodeToString(xBytes),
				"y":   base64.RawURLEncoding.EncodeToString(yBytes),
			},
		},
	})
	if err != nil {
		t.Fatalf("json.Marshal(iapJWKS) failed: %v", err)
	}

	client := &http.Client{
		Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			var body []byte
			switch req.URL.String() {
			case "https://www.googleapis.com/oauth2/v3/certs":
				body = oidcJWKS
			case "https://www.gstatic.com/iap/verify/public_key-jwk":
				body = iapJWKS
			default:
				return &http.Response{
					StatusCode: http.StatusNotFound,
					Body:       io.NopCloser(strings.NewReader("not found")),
					Header:     make(http.Header),
				}, nil
			}
			hdr := make(http.Header)
			hdr.Set("Content-Type", "application/json")
			hdr.Set("Cache-Control", "public, max-age=3600")
			return &http.Response{
				StatusCode: http.StatusOK,
				Body:       io.NopCloser(bytes.NewReader(body)),
				Header:     hdr,
			}, nil
		}),
	}

	return &testKeySet{
		rsaKey:     rsaKey,
		ecKey:      ecKey,
		httpClient: client,
	}
}

func (ks *testKeySet) signRS256(t *testing.T, claims map[string]any) string {
	t.Helper()
	headerJSON, err := json.Marshal(map[string]string{
		"alg": "RS256",
		"typ": "JWT",
		"kid": testOIDCKeyID,
	})
	if err != nil {
		t.Fatalf("json.Marshal(header) failed: %v", err)
	}
	payloadJSON, err := json.Marshal(claims)
	if err != nil {
		t.Fatalf("json.Marshal(claims) failed: %v", err)
	}
	signingInput := base64.RawURLEncoding.EncodeToString(headerJSON) + "." + base64.RawURLEncoding.EncodeToString(payloadJSON)
	digest := sha256.Sum256([]byte(signingInput))
	sig, err := rsa.SignPKCS1v15(rand.Reader, ks.rsaKey, crypto.SHA256, digest[:])
	if err != nil {
		t.Fatalf("rsa.SignPKCS1v15() failed: %v", err)
	}
	return signingInput + "." + base64.RawURLEncoding.EncodeToString(sig)
}

func (ks *testKeySet) signES256(t *testing.T, claims map[string]any) string {
	t.Helper()
	headerJSON, err := json.Marshal(map[string]string{
		"alg": "ES256",
		"typ": "JWT",
		"kid": testIAPKeyID,
	})
	if err != nil {
		t.Fatalf("json.Marshal(header) failed: %v", err)
	}
	payloadJSON, err := json.Marshal(claims)
	if err != nil {
		t.Fatalf("json.Marshal(claims) failed: %v", err)
	}
	signingInput := base64.RawURLEncoding.EncodeToString(headerJSON) + "." + base64.RawURLEncoding.EncodeToString(payloadJSON)
	digest := sha256.Sum256([]byte(signingInput))
	r, s, err := ecdsa.Sign(rand.Reader, ks.ecKey, digest[:])
	if err != nil {
		t.Fatalf("ecdsa.Sign() failed: %v", err)
	}
	sig := make([]byte, 64)
	r.FillBytes(sig[:32])
	s.FillBytes(sig[32:])
	return signingInput + "." + base64.RawURLEncoding.EncodeToString(sig)
}

func newProtectedTestRouter(t *testing.T, opts Options) *gin.Engine {
	t.Helper()
	gin.SetMode(gin.TestMode)
	mw, err := NewMiddleware(t.Context(), opts)
	if err != nil {
		t.Fatalf("NewMiddleware() failed: %v", err)
	}
	r := gin.New()
	r.GET("/protected", mw, func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"userID":           c.GetString("userID"),
			"userEmail":        c.GetString("userEmail"),
			"verifiedEmail":    c.GetBool("verifiedEmail"),
			"userHostedDomain": c.GetString("userHostedDomain"),
		})
	})
	return r
}

func TestMiddlewareAuthenticatedSuccess(t *testing.T) {
	ks := newTestKeySet(t)
	exp := time.Now().Add(10 * time.Minute).Unix()

	validOIDC := ks.signRS256(t, map[string]any{
		"iss":            "https://accounts.google.com",
		"sub":            "10987654321",
		"aud":            testClientID,
		"exp":            exp,
		"iat":            exp - 600,
		"email":          "alice@example.com",
		"email_verified": true,
		"hd":             "example.com",
	})
	validOIDCPlainIssuer := ks.signRS256(t, map[string]any{
		"iss":   "accounts.google.com",
		"sub":   "sa-subject-1",
		"aud":   testClientID,
		"exp":   exp,
		"email": "sa@project.iam.gserviceaccount.com",
	})
	validIAP := ks.signES256(t, map[string]any{
		"iss":   "https://cloud.google.com/iap",
		"sub":   "accounts.google.com:998877",
		"aud":   testIAPAudience,
		"exp":   exp,
		"email": "workflow-sa@project.iam.gserviceaccount.com",
		"hd":    "example.com",
	})

	tests := []struct {
		name        string
		opts        Options
		headers     map[string]string
		secretToken string
		wantUserID  string
		wantEmail   string
		wantDomain  string
	}{
		{
			name: "oidc_bearer_with_allowed_domain",
			opts: Options{
				GoogleClientID: testClientID,
				AllowedDomain:  "example.com",
				HTTPClient:     ks.httpClient,
			},
			headers: map[string]string{
				"Authorization": "Bearer " + validOIDC,
			},
			secretToken: validOIDC,
			wantUserID:  "10987654321",
			wantEmail:   "alice@example.com",
			wantDomain:  "example.com",
		},
		{
			name: "oidc_plain_accounts_issuer_service_account",
			opts: Options{
				GoogleClientID: testClientID,
				HTTPClient:     ks.httpClient,
			},
			headers: map[string]string{
				"Authorization": "bearer " + validOIDCPlainIssuer,
			},
			secretToken: validOIDCPlainIssuer,
			wantUserID:  "sa-subject-1",
			wantEmail:   "sa@project.iam.gserviceaccount.com",
		},
		{
			name: "iap_signed_assertion_header",
			opts: Options{
				IAPAudience:   testIAPAudience,
				AllowedDomain: "EXAMPLE.COM",
				HTTPClient:    ks.httpClient,
			},
			headers: map[string]string{
				IAPAssertionHeader: validIAP,
			},
			secretToken: validIAP,
			wantUserID:  "accounts.google.com:998877",
			wantEmail:   "workflow-sa@project.iam.gserviceaccount.com",
			wantDomain:  "example.com",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			var logBuf bytes.Buffer
			opts := tc.opts
			opts.Logger = log.New(&logBuf, "", 0)

			mw, err := NewMiddleware(t.Context(), opts)
			if err != nil {
				t.Fatalf("NewMiddleware() failed: %v", err)
			}
			gin.SetMode(gin.TestMode)
			r := gin.New()
			r.GET("/protected", mw, func(c *gin.Context) {
				c.JSON(http.StatusOK, gin.H{
					"userID":           c.GetString("userID"),
					"userEmail":        c.GetString("userEmail"),
					"userHostedDomain": c.GetString("userHostedDomain"),
				})
			})

			req := httptest.NewRequestWithContext(t.Context(), http.MethodGet, "/protected", nil)
			for k, v := range tc.headers {
				req.Header.Set(k, v)
			}
			rec := httptest.NewRecorder()
			r.ServeHTTP(rec, req)

			if rec.Code != http.StatusOK {
				t.Fatalf("GET /protected status = %d, want %d; body = %s", rec.Code, http.StatusOK, rec.Body.String())
			}

			var got map[string]any
			if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
				t.Fatalf("json.Unmarshal(response) failed: %v", err)
			}
			if got["userID"] != tc.wantUserID {
				t.Errorf("GET /protected userID = %v, want %q", got["userID"], tc.wantUserID)
			}
			if got["userEmail"] != tc.wantEmail {
				t.Errorf("GET /protected userEmail = %v, want %q", got["userEmail"], tc.wantEmail)
			}
			if got["userHostedDomain"] != tc.wantDomain {
				t.Errorf("GET /protected userHostedDomain = %v, want %q", got["userHostedDomain"], tc.wantDomain)
			}
			if strings.Contains(logBuf.String(), tc.secretToken) {
				t.Errorf("middleware log output leaked raw token (CWE-532): %q", logBuf.String())
			}
		})
	}
}

func TestMiddlewareRejections(t *testing.T) {
	ks := newTestKeySet(t)
	now := time.Now()

	validOIDC := ks.signRS256(t, map[string]any{
		"iss": "https://accounts.google.com",
		"sub": "user-1",
		"aud": testClientID,
		"exp": now.Add(10 * time.Minute).Unix(),
		"hd":  "other.example.com",
	})
	expiredOIDC := ks.signRS256(t, map[string]any{
		"iss": "https://accounts.google.com",
		"sub": "user-1",
		"aud": testClientID,
		"exp": now.Add(-5 * time.Minute).Unix(),
	})
	wrongAudOIDC := ks.signRS256(t, map[string]any{
		"iss": "https://accounts.google.com",
		"sub": "user-1",
		"aud": "wrong-audience.apps.googleusercontent.com",
		"exp": now.Add(10 * time.Minute).Unix(),
	})
	wrongIssuerOIDC := ks.signRS256(t, map[string]any{
		"iss": "https://evil.example.com",
		"sub": "user-1",
		"aud": testClientID,
		"exp": now.Add(10 * time.Minute).Unix(),
	})
	oidcWithIAPAud := ks.signRS256(t, map[string]any{
		"iss": "https://accounts.google.com",
		"sub": "user-1",
		"aud": testIAPAudience,
		"exp": now.Add(10 * time.Minute).Unix(),
	})
	iapWithOIDCAud := ks.signES256(t, map[string]any{
		"iss": "https://cloud.google.com/iap",
		"sub": "user-1",
		"aud": testClientID,
		"exp": now.Add(10 * time.Minute).Unix(),
	})

	tests := []struct {
		name       string
		opts       Options
		headers    map[string]string
		leakCheck  string
		wantStatus int
	}{
		{
			name: "fails_closed_when_no_audience_configured",
			opts: Options{
				HTTPClient: ks.httpClient,
			},
			headers: map[string]string{
				"Authorization": "Bearer " + validOIDC,
			},
			leakCheck:  validOIDC,
			wantStatus: http.StatusUnauthorized,
		},
		{
			name: "missing_authorization_header_in_oidc_mode",
			opts: Options{
				GoogleClientID: testClientID,
				HTTPClient:     ks.httpClient,
			},
			wantStatus: http.StatusUnauthorized,
		},
		{
			name: "malformed_authorization_scheme",
			opts: Options{
				GoogleClientID: testClientID,
				HTTPClient:     ks.httpClient,
			},
			headers: map[string]string{
				"Authorization": "Basic secret-basic-creds",
			},
			leakCheck:  "secret-basic-creds",
			wantStatus: http.StatusUnauthorized,
		},
		{
			name: "bearer_without_token",
			opts: Options{
				GoogleClientID: testClientID,
				HTTPClient:     ks.httpClient,
			},
			headers: map[string]string{
				"Authorization": "Bearer   ",
			},
			wantStatus: http.StatusUnauthorized,
		},
		{
			name: "bearer_with_embedded_whitespace",
			opts: Options{
				GoogleClientID: testClientID,
				HTTPClient:     ks.httpClient,
			},
			headers: map[string]string{
				"Authorization": "Bearer tok1 tok2",
			},
			leakCheck:  "tok1",
			wantStatus: http.StatusUnauthorized,
		},
		{
			name: "expired_oidc_token",
			opts: Options{
				GoogleClientID: testClientID,
				HTTPClient:     ks.httpClient,
			},
			headers: map[string]string{
				"Authorization": "Bearer " + expiredOIDC,
			},
			leakCheck:  expiredOIDC,
			wantStatus: http.StatusUnauthorized,
		},
		{
			name: "wrong_oidc_audience",
			opts: Options{
				GoogleClientID: testClientID,
				HTTPClient:     ks.httpClient,
			},
			headers: map[string]string{
				"Authorization": "Bearer " + wrongAudOIDC,
			},
			leakCheck:  wrongAudOIDC,
			wantStatus: http.StatusUnauthorized,
		},
		{
			name: "wrong_oidc_issuer",
			opts: Options{
				GoogleClientID: testClientID,
				HTTPClient:     ks.httpClient,
			},
			headers: map[string]string{
				"Authorization": "Bearer " + wrongIssuerOIDC,
			},
			leakCheck:  wrongIssuerOIDC,
			wantStatus: http.StatusUnauthorized,
		},
		{
			name: "iap_token_stuffed_into_bearer_header_rejected",
			opts: Options{
				GoogleClientID: testClientID,
				HTTPClient:     ks.httpClient,
			},
			headers: map[string]string{
				"Authorization": "Bearer " + iapWithOIDCAud,
			},
			leakCheck:  iapWithOIDCAud,
			wantStatus: http.StatusUnauthorized,
		},
		{
			name: "oidc_token_stuffed_into_iap_header_rejected",
			opts: Options{
				IAPAudience: testIAPAudience,
				HTTPClient:  ks.httpClient,
			},
			headers: map[string]string{
				IAPAssertionHeader: oidcWithIAPAud,
			},
			leakCheck:  oidcWithIAPAud,
			wantStatus: http.StatusUnauthorized,
		},
		{
			name: "missing_iap_header_in_iap_only_mode",
			opts: Options{
				IAPAudience: testIAPAudience,
				HTTPClient:  ks.httpClient,
			},
			headers: map[string]string{
				"Authorization": "Bearer " + validOIDC,
			},
			leakCheck:  validOIDC,
			wantStatus: http.StatusUnauthorized,
		},
		{
			name: "forged_iap_header_does_not_fallback_to_bearer_in_hybrid_mode",
			opts: Options{
				IAPAudience:    testIAPAudience,
				GoogleClientID: testClientID,
				HTTPClient:     ks.httpClient,
			},
			headers: map[string]string{
				IAPAssertionHeader: "forged.iap.jwt",
				"Authorization":    "Bearer " + validOIDC,
			},
			leakCheck:  "forged.iap.jwt",
			wantStatus: http.StatusUnauthorized,
		},
		{
			name: "mismatched_hosted_domain_returns_403",
			opts: Options{
				GoogleClientID: testClientID,
				AllowedDomain:  "corp.example.com",
				HTTPClient:     ks.httpClient,
			},
			headers: map[string]string{
				"Authorization": "Bearer " + validOIDC,
			},
			leakCheck:  validOIDC,
			wantStatus: http.StatusForbidden,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			var logBuf bytes.Buffer
			opts := tc.opts
			opts.Logger = log.New(&logBuf, "", 0)

			mw, err := NewMiddleware(t.Context(), opts)
			if err != nil {
				t.Fatalf("NewMiddleware() failed: %v", err)
			}
			gin.SetMode(gin.TestMode)
			r := gin.New()
			handlerCalled := false
			r.GET("/protected", mw, func(c *gin.Context) {
				handlerCalled = true
				c.Status(http.StatusOK)
			})

			req := httptest.NewRequestWithContext(t.Context(), http.MethodGet, "/protected", nil)
			for k, v := range tc.headers {
				req.Header.Set(k, v)
			}
			rec := httptest.NewRecorder()
			r.ServeHTTP(rec, req)

			if rec.Code != tc.wantStatus {
				t.Errorf("GET /protected status = %d, want %d; body = %s", rec.Code, tc.wantStatus, rec.Body.String())
			}
			if handlerCalled {
				t.Errorf("protected handler was executed on rejected request (status %d)", rec.Code)
			}
			if tc.leakCheck != "" && strings.Contains(logBuf.String(), tc.leakCheck) {
				t.Errorf("middleware log output leaked raw token %q in %q", tc.leakCheck, logBuf.String())
			}
		})
	}
}

func TestMiddlewareDynamicIAPAudienceFile(t *testing.T) {
	ks := newTestKeySet(t)
	audPath := filepath.Join(t.TempDir(), "iap_audience")

	validIAP := ks.signES256(t, map[string]any{
		"iss": "https://cloud.google.com/iap",
		"sub": "accounts.google.com:42",
		"aud": testIAPAudience,
		"exp": time.Now().Add(10 * time.Minute).Unix(),
	})

	router := newProtectedTestRouter(t, Options{
		IAPAudienceFile: audPath,
		HTTPClient:      ks.httpClient,
	})

	// Before ConfigMap file exists, /protected must fail closed with 401.
	reqBefore := httptest.NewRequestWithContext(t.Context(), http.MethodGet, "/protected", nil)
	reqBefore.Header.Set(IAPAssertionHeader, validIAP)
	recBefore := httptest.NewRecorder()
	router.ServeHTTP(recBefore, reqBefore)
	if recBefore.Code != http.StatusUnauthorized {
		t.Fatalf("GET /protected before audience file exists = %d, want %d", recBefore.Code, http.StatusUnauthorized)
	}

	// Once the ConfigMap projects iap_audience onto disk, requests succeed without server restart.
	if err := os.WriteFile(audPath, []byte(testIAPAudience+"\n"), 0o600); err != nil {
		t.Fatalf("os.WriteFile(%q) failed: %v", audPath, err)
	}

	reqAfter := httptest.NewRequestWithContext(t.Context(), http.MethodGet, "/protected", nil)
	reqAfter.Header.Set(IAPAssertionHeader, validIAP)
	recAfter := httptest.NewRecorder()
	router.ServeHTTP(recAfter, reqAfter)
	if recAfter.Code != http.StatusOK {
		t.Fatalf("GET /protected after audience file populated = %d, want %d; body = %s", recAfter.Code, http.StatusOK, recAfter.Body.String())
	}
}
