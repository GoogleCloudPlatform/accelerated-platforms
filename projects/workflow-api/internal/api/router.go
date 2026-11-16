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

// Package api configures HTTP routing and handlers for the workflow-api service.
package api

import (
	"comfyui-api-service/comfyui"
	"comfyui-api-service/internal/auth"
	"comfyui-api-service/internal/config"
	"context"
	"fmt"
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
	swaggerFiles "github.com/swaggo/files"
	ginSwagger "github.com/swaggo/gin-swagger"
)

// RouterOptions configures optional dependencies for SetupRouterWithOptions.
type RouterOptions struct {
	AuthHTTPClient *http.Client
	AuthLogger     *log.Logger
}

// SetupRouter configures the Gin router with authentication middleware and routes.
func SetupRouter(ctx context.Context, cfg *config.Config, comfyClient *comfyui.Client) (*gin.Engine, error) {
	return SetupRouterWithOptions(ctx, cfg, comfyClient, RouterOptions{})
}

// SetupRouterWithOptions configures the Gin router with explicit authentication options.
func SetupRouterWithOptions(ctx context.Context, cfg *config.Config, comfyClient *comfyui.Client, opts RouterOptions) (*gin.Engine, error) {
	gin.SetMode(cfg.GinMode)
	router := gin.Default()

	// Health check endpoint remains unauthenticated for load balancer and Kubernetes probes.
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "UP"})
	})

	if cfg.EnableSwagger {
		swaggerURL := ginSwagger.URL("/swagger/doc.json")
		router.GET("/swagger/*any", ginSwagger.WrapHandler(swaggerFiles.Handler, swaggerURL,
			ginSwagger.PersistAuthorization(true),
		))
	}

	authMiddleware, err := auth.NewMiddleware(ctx, auth.Options{
		GoogleClientID:  cfg.GoogleClientID,
		IAPAudience:     cfg.IAPAudience,
		IAPAudienceFile: cfg.IAPAudienceFile,
		AllowedDomain:   cfg.AllowedAuthDomain,
		HTTPClient:      opts.AuthHTTPClient,
		Logger:          opts.AuthLogger,
	})
	if err != nil {
		return nil, fmt.Errorf("initializing auth middleware: %v", err)
	}

	apiHandler := NewAPIHandler(comfyClient)

	// All /api/v1 routes enforce IAP signed-header or Google OIDC Bearer authentication.
	v1 := router.Group("/api/v1")
	v1.Use(authMiddleware)
	{
		v1.POST("/queue_prompt", apiHandler.QueuePrompt)
		v1.GET("/history/:prompt_id", apiHandler.GetHistory)
		v1.GET("/image", apiHandler.GetImage)
		v1.POST("/upload_image", apiHandler.UploadImage)
	}

	return router, nil
}
