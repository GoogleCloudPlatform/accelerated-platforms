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

// Package config loads and validates runtime configuration from environment variables.
package config

import (
	"errors"
	"fmt"
	"log"
	"net/url"
	"os"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
)

// Config holds runtime settings for the workflow-api HTTP server.
type Config struct {
	ComfyUIBaseURL    string
	GoogleClientID    string
	IAPAudience       string
	IAPAudienceFile   string
	AllowedAuthDomain string
	ServerPort        string
	GinMode           string
	EnableSwagger     bool
}

// Load reads server configuration from an optional .env file and environment variables.
func Load() (*Config, error) {
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found, reading environment variables directly")
	}

	ginMode := strings.TrimSpace(getEnv("GIN_MODE", gin.ReleaseMode))
	defaultSwagger := ginMode != gin.ReleaseMode
	enableSwagger, err := getEnvBool("ENABLE_SWAGGER", defaultSwagger)
	if err != nil {
		return nil, err
	}

	cfg := &Config{
		ComfyUIBaseURL:    strings.TrimSpace(getEnv("COMFYUI_BASE_URL", "http://127.0.0.1:8188")),
		GoogleClientID:    strings.TrimSpace(getEnv("GOOGLE_CLIENT_ID", "")),
		IAPAudience:       strings.TrimSpace(getEnv("IAP_AUDIENCE", "")),
		IAPAudienceFile:   strings.TrimSpace(getEnv("IAP_AUDIENCE_FILE", "")),
		AllowedAuthDomain: strings.TrimSpace(getEnv("ALLOWED_AUTH_DOMAIN", "")),
		ServerPort:        strings.TrimSpace(getEnv("SERVER_PORT", "8080")),
		GinMode:           ginMode,
		EnableSwagger:     enableSwagger,
	}

	if err := cfg.Validate(); err != nil {
		return nil, err
	}
	return cfg, nil
}

// Validate checks that required server settings are well-formed.
func (c *Config) Validate() error {
	if c.ComfyUIBaseURL == "" {
		return errors.New("COMFYUI_BASE_URL must not be empty")
	}
	parsedURL, err := url.Parse(c.ComfyUIBaseURL)
	if err != nil || (parsedURL.Scheme != "http" && parsedURL.Scheme != "https") || parsedURL.Host == "" {
		return fmt.Errorf("invalid COMFYUI_BASE_URL %q: must be an http or https URL", c.ComfyUIBaseURL)
	}
	if c.ServerPort == "" {
		return errors.New("SERVER_PORT must not be empty")
	}
	return nil
}

// HasAuthConfig reports whether at least one authentication audience source is configured.
func (c *Config) HasAuthConfig() bool {
	return c.GoogleClientID != "" || c.IAPAudience != "" || c.IAPAudienceFile != ""
}

func getEnv(key, fallback string) string {
	if value, exists := os.LookupEnv(key); exists {
		return value
	}
	return fallback
}

func getEnvBool(key string, fallback bool) (bool, error) {
	raw, exists := os.LookupEnv(key)
	if !exists || strings.TrimSpace(raw) == "" {
		return fallback, nil
	}
	parsed, err := strconv.ParseBool(strings.TrimSpace(raw))
	if err != nil {
		return false, fmt.Errorf("invalid boolean value %q for %s: %v", raw, key, err)
	}
	return parsed, nil
}
