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

// Package auth provides Gin authentication middleware for IAP and Google OIDC tokens.
package auth

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"

	"github.com/gin-gonic/gin"
	"google.golang.org/api/idtoken"
	"google.golang.org/api/option"
)

const (
	// IAPAssertionHeader is the HTTP header injected by Identity-Aware Proxy containing a signed JWT.
	IAPAssertionHeader = "X-Goog-IAP-JWT-Assertion"

	iapIssuer         = "https://cloud.google.com/iap"
	googleIssuerHTTPS = "https://accounts.google.com"
	googleIssuerPlain = "accounts.google.com"
	maxAudienceBytes  = 4096
)

// Options configures JWT verification for NewMiddleware.
type Options struct {
	GoogleClientID  string
	IAPAudience     string
	IAPAudienceFile string
	AllowedDomain   string
	HTTPClient      *http.Client
	Logger          *log.Logger
}

// NewMiddleware creates a Gin middleware that enforces cryptographic JWT verification
// via Identity-Aware Proxy signed headers (ES256) and/or Google OIDC Bearer ID tokens (RS256).
// If neither audience is configured at request time, all requests fail closed with HTTP 401.
func NewMiddleware(ctx context.Context, opts Options) (gin.HandlerFunc, error) {
	var validatorOpts []option.ClientOption
	if opts.HTTPClient != nil {
		validatorOpts = append(validatorOpts, option.WithHTTPClient(opts.HTTPClient))
	}

	validator, err := idtoken.NewValidator(ctx, validatorOpts...)
	if err != nil {
		return nil, fmt.Errorf("creating ID token validator: %v", err)
	}

	logger := opts.Logger
	if logger == nil {
		logger = log.Default()
	}

	googleClientID := strings.TrimSpace(opts.GoogleClientID)
	staticIAPAudience := strings.TrimSpace(opts.IAPAudience)
	iapAudienceFile := strings.TrimSpace(opts.IAPAudienceFile)
	allowedDomain := strings.TrimSpace(opts.AllowedDomain)

	return func(c *gin.Context) {
		iapAudience := staticIAPAudience
		if iapAudience == "" && iapAudienceFile != "" {
			loaded, readErr := readAudienceFile(iapAudienceFile)
			if readErr != nil && !errors.Is(readErr, os.ErrNotExist) {
				logger.Printf("Failed reading IAP audience file %q: %v", iapAudienceFile, readErr)
			}
			iapAudience = loaded
		}

		if iapAudience == "" && googleClientID == "" {
			logger.Printf("Authentication rejected: neither IAP audience nor GOOGLE_CLIENT_ID is configured")
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "Service authentication is not configured"})
			return
		}

		var payload *idtoken.Payload

		iapToken := strings.TrimSpace(c.GetHeader(IAPAssertionHeader))
		switch {
		case iapToken != "" && iapAudience != "":
			validated, valErr := validateIAPToken(c.Request.Context(), validator, iapToken, iapAudience)
			if valErr != nil {
				logger.Printf("IAP token validation failed: %v", valErr)
				c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "Invalid IAP authentication assertion"})
				return
			}
			payload = validated

		case googleClientID != "":
			bearerToken, hdrErr := extractBearerToken(c.GetHeader("Authorization"))
			if hdrErr != nil {
				c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": hdrErr.Error()})
				return
			}
			validated, valErr := validateOIDCToken(c.Request.Context(), validator, bearerToken, googleClientID)
			if valErr != nil {
				logger.Printf("Bearer token validation failed: %v", valErr)
				c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "Invalid or expired Bearer token"})
				return
			}
			payload = validated

		default:
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "IAP authentication assertion required"})
			return
		}

		hostedDomain, _ := payload.Claims["hd"].(string)
		email, _ := payload.Claims["email"].(string)
		verifiedEmail, _ := payload.Claims["email_verified"].(bool)

		if allowedDomain != "" && !strings.EqualFold(hostedDomain, allowedDomain) {
			logger.Printf("Domain mismatch: got %q, want %q for subject %q", hostedDomain, allowedDomain, payload.Subject)
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{
				"error": fmt.Sprintf("Access restricted to domain %q", allowedDomain),
			})
			return
		}

		c.Set("userID", payload.Subject)
		c.Set("userEmail", email)
		c.Set("verifiedEmail", verifiedEmail)
		c.Set("userHostedDomain", hostedDomain)

		c.Next()
	}, nil
}

func validateIAPToken(ctx context.Context, validator *idtoken.Validator, token, audience string) (*idtoken.Payload, error) {
	payload, err := validator.Validate(ctx, token, audience)
	if err != nil {
		return nil, fmt.Errorf("verifying IAP JWT: %v", err)
	}
	if payload.Issuer != iapIssuer {
		return nil, fmt.Errorf("unexpected IAP issuer %q", payload.Issuer)
	}
	return payload, nil
}

func validateOIDCToken(ctx context.Context, validator *idtoken.Validator, token, audience string) (*idtoken.Payload, error) {
	payload, err := validator.Validate(ctx, token, audience)
	if err != nil {
		return nil, fmt.Errorf("verifying OIDC JWT: %v", err)
	}
	if payload.Issuer != googleIssuerHTTPS && payload.Issuer != googleIssuerPlain {
		return nil, fmt.Errorf("unexpected OIDC issuer %q", payload.Issuer)
	}
	return payload, nil
}

func extractBearerToken(authHeader string) (string, error) {
	trimmed := strings.TrimSpace(authHeader)
	if trimmed == "" {
		return "", errors.New("Authorization header required")
	}
	scheme, token, ok := strings.Cut(trimmed, " ")
	token = strings.TrimSpace(token)
	if !ok || !strings.EqualFold(scheme, "bearer") || token == "" || strings.ContainsAny(token, " \t\r\n") {
		return "", errors.New("Authorization header format must be 'Bearer {token}'")
	}
	return token, nil
}

func readAudienceFile(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()

	data, err := io.ReadAll(io.LimitReader(f, maxAudienceBytes))
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(data)), nil
}
