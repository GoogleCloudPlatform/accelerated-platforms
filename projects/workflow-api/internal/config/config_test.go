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

package config

import (
	"testing"
)

func clearConfigEnv(t *testing.T) {
	t.Helper()
	keys := []string{
		"COMFYUI_BASE_URL",
		"GOOGLE_CLIENT_ID",
		"IAP_AUDIENCE",
		"IAP_AUDIENCE_FILE",
		"ALLOWED_AUTH_DOMAIN",
		"SERVER_PORT",
		"GIN_MODE",
		"ENABLE_SWAGGER",
	}
	for _, k := range keys {
		t.Setenv(k, "")
	}
}

func TestLoadDefaults(t *testing.T) {
	clearConfigEnv(t)
	// Unset keys so fallback defaults apply where os.LookupEnv checks existence.
	t.Setenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188")
	t.Setenv("SERVER_PORT", "8080")
	t.Setenv("GIN_MODE", "release")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load() unexpected error: %v", err)
	}
	if cfg.ComfyUIBaseURL != "http://127.0.0.1:8188" {
		t.Errorf("Load().ComfyUIBaseURL = %q, want %q", cfg.ComfyUIBaseURL, "http://127.0.0.1:8188")
	}
	if cfg.ServerPort != "8080" {
		t.Errorf("Load().ServerPort = %q, want %q", cfg.ServerPort, "8080")
	}
	if cfg.GinMode != "release" {
		t.Errorf("Load().GinMode = %q, want %q", cfg.GinMode, "release")
	}
	if cfg.EnableSwagger {
		t.Errorf("Load().EnableSwagger = %v, want false in release mode", cfg.EnableSwagger)
	}
	if cfg.HasAuthConfig() {
		t.Errorf("cfg.HasAuthConfig() = %v, want false when auth env vars are empty", cfg.HasAuthConfig())
	}
}

func TestLoadCustomValues(t *testing.T) {
	tests := []struct {
		name              string
		env               map[string]string
		wantSwagger       bool
		wantHasAuthConfig bool
	}{
		{
			name: "debug_enables_swagger_and_oidc_client",
			env: map[string]string{
				"COMFYUI_BASE_URL":    "https://comfyui.internal:8188",
				"GOOGLE_CLIENT_ID":    "client-123.apps.googleusercontent.com",
				"ALLOWED_AUTH_DOMAIN": "example.com",
				"SERVER_PORT":         "9090",
				"GIN_MODE":            "debug",
			},
			wantSwagger:       true,
			wantHasAuthConfig: true,
		},
		{
			name: "iap_audience_with_explicit_swagger_override",
			env: map[string]string{
				"COMFYUI_BASE_URL": "http://comfyui.comfyui.svc.cluster.local:8188",
				"IAP_AUDIENCE":     "/projects/111/global/backendServices/222",
				"SERVER_PORT":      "8080",
				"GIN_MODE":         "release",
				"ENABLE_SWAGGER":   "true",
			},
			wantSwagger:       true,
			wantHasAuthConfig: true,
		},
		{
			name: "iap_audience_file_counts_as_auth_config",
			env: map[string]string{
				"COMFYUI_BASE_URL":  "http://127.0.0.1:8188",
				"IAP_AUDIENCE_FILE": "/etc/workflow-api/iap/iap_audience",
				"SERVER_PORT":       "8080",
				"GIN_MODE":          "debug",
				"ENABLE_SWAGGER":    "false",
			},
			wantSwagger:       false,
			wantHasAuthConfig: true,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			clearConfigEnv(t)
			for k, v := range tc.env {
				t.Setenv(k, v)
			}

			cfg, err := Load()
			if err != nil {
				t.Fatalf("Load() unexpected error: %v", err)
			}
			if cfg.EnableSwagger != tc.wantSwagger {
				t.Errorf("Load().EnableSwagger = %v, want %v", cfg.EnableSwagger, tc.wantSwagger)
			}
			if got := cfg.HasAuthConfig(); got != tc.wantHasAuthConfig {
				t.Errorf("cfg.HasAuthConfig() = %v, want %v", got, tc.wantHasAuthConfig)
			}
		})
	}
}

func TestLoadErrors(t *testing.T) {
	tests := []struct {
		name string
		env  map[string]string
	}{
		{
			name: "empty_comfyui_url",
			env: map[string]string{
				"COMFYUI_BASE_URL": "",
				"SERVER_PORT":      "8080",
			},
		},
		{
			name: "unsupported_comfyui_scheme",
			env: map[string]string{
				"COMFYUI_BASE_URL": "ftp://127.0.0.1:8188",
				"SERVER_PORT":      "8080",
			},
		},
		{
			name: "missing_comfyui_host",
			env: map[string]string{
				"COMFYUI_BASE_URL": "http://",
				"SERVER_PORT":      "8080",
			},
		},
		{
			name: "empty_server_port",
			env: map[string]string{
				"COMFYUI_BASE_URL": "http://127.0.0.1:8188",
				"SERVER_PORT":      "   ",
			},
		},
		{
			name: "invalid_enable_swagger_bool",
			env: map[string]string{
				"COMFYUI_BASE_URL": "http://127.0.0.1:8188",
				"SERVER_PORT":      "8080",
				"ENABLE_SWAGGER":   "not-a-bool",
			},
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			clearConfigEnv(t)
			for k, v := range tc.env {
				t.Setenv(k, v)
			}

			if cfg, err := Load(); err == nil {
				t.Errorf("Load() = %+v, nil; want non-nil error", cfg)
			}
		})
	}
}
