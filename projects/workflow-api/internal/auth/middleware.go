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
	"context"
	"fmt"
	"log"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
	"google.golang.org/api/oauth2/v2"
	"google.golang.org/api/option"
)

// AuthMiddleware creates a Gin middleware for Google OAuth token validation.
// It verifies Bearer tokens using Google's tokeninfo endpoint and then
// retrieves user details including the G Suite domain (hd claim) from the userinfo endpoint.
func AuthMiddleware(googleClientID string, allowedDomain string) gin.HandlerFunc {
	oauth2Service, err := oauth2.NewService(context.Background(), option.WithoutAuthentication())
	if err != nil {
		log.Fatalf("Failed to create Google OAuth2 service: %v", err)
	}

	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "Authorization header required"})
			return
		}

		parts := strings.Split(authHeader, " ")
		if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "Authorization header format must be 'Bearer {token}'"})
			return
		}
		token := parts[1]

		fmt.Printf("Received token: %s\n", token)

		// Validate the access token using the tokeninfo endpoint
		tokenInfoCall := oauth2Service.Tokeninfo()
		tokenInfoCall.AccessToken(token)

		tokenInfo, err := tokenInfoCall.Do()
		if err != nil {
			log.Printf("Token validation error: %v", err)
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "Invalid token or token validation failed"})
			return
		}

		if tokenInfo.Audience != googleClientID {
			log.Printf("Token audience mismatch. Expected: %s, Got: %s, User: %s", googleClientID, tokenInfo.Audience, tokenInfo.Email)
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "Invalid token audience. Token not intended for this application."})
			return
		}

		if tokenInfo.ExpiresIn <= 0 {
			log.Printf("Expired token received for User: %s, Audience: %s", tokenInfo.Email, tokenInfo.Audience)
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "Token expired"})
			return
		}

		// Now, retrieve user details from the userinfo endpoint to get the 'hd' (hosted domain) claim
		// The Userinfo service is part of the oauth2/v2 package.
		userinfoService := oauth2.NewUserinfoService(oauth2Service)
		userInfo, err := userinfoService.Get().Do() // This uses the context from the oauth2Service
		if err != nil {
			log.Printf("Failed to retrieve userinfo: %v", err)
			// If userinfo cannot be retrieved, it's a server-side issue or an invalid token for userinfo
			c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve user details for domain validation."})
			return
		}

		// Optional: Restrict access to a specific G Suite domain (hd claim).
		if allowedDomain != "" {
			// userInfo.Hd contains the G Suite domain, if present.
			if userInfo.Hd != allowedDomain {
				log.Printf("Domain mismatch. Expected: %s, User's domain (hd claim): '%s', User Email: %s", allowedDomain, userInfo.Hd, userInfo.Email)
				userDomainMsg := userInfo.Hd
				if userDomainMsg == "" {
					userDomainMsg = "(not provided or not a G Suite account)"
				}
				c.AbortWithStatusJSON(http.StatusForbidden, gin.H{"error": fmt.Sprintf("Access restricted. User's domain '%s' is not allowed. Required domain: '%s'", userDomainMsg, allowedDomain)})
				return
			}
		}

		// Set user information in Gin context
		c.Set("userID", tokenInfo.UserId)
		c.Set("userEmail", tokenInfo.Email)
		c.Set("verifiedEmail", tokenInfo.VerifiedEmail)
		c.Set("tokenScopes", tokenInfo.Scope)
		c.Set("userHostedDomain", userInfo.Hd) // Set the hosted domain if available

		c.Next() // Proceed to the next handler
	}
}
