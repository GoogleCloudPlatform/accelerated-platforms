package main

import (
	"comfyui-api-service/comfyui"
	"comfyui-api-service/internal/api"
	"comfyui-api-service/internal/config"
	"fmt"
	"log"
)

// @title           ComfyUI API Service via Gin
// @version         1.0
// @description     Exposes ComfyUI client functions as a RESTful API secured by Google OAuth.
// @termsOfService  http://swagger.io/terms/

// @contact.name   API Support
// @contact.url    http://www.swagger.io/support
// @contact.email  support@swagger.io

// @license.name  Apache 2.0
// @license.url   http://www.apache.org/licenses/LICENSE-2.0.html

// @host            localhost:8080
// @BasePath        /api/v1

// @securityDefinitions.apikey BearerAuth
// @in header
// @name Authorization
// @description Type "Bearer" followed by a space and a valid Google OAuth access token. Example: "Bearer y29..."

// @externalDocs.description  OpenAPI
// @externalDocs.url          https://swagger.io/resources/open-api/
func main() {
	// Load configuration
	cfg := config.LoadConfig()

	// Create ComfyUI client instance
	comfyClient, err := comfyui.NewClient(cfg.ComfyUIBaseURL)
	if err != nil {
		log.Fatalf("Failed to create ComfyUI client: %v", err)
	}
	// Optional: Customize client timeout if needed
	// comfyClient.SetTimeout(90 * time.Second)

	// Setup Gin router
	router := api.SetupRouter(cfg, comfyClient)

	// Start server
	serverAddr := fmt.Sprintf(":%s", cfg.ServerPort)
	log.Printf("Starting server on %s in %s mode", serverAddr, cfg.GinMode)
	log.Printf("ComfyUI Backend URL: %s", cfg.ComfyUIBaseURL)
	log.Printf("Google Client ID: %s", cfg.GoogleClientID)
	if cfg.AllowedAuthDomain != "" {
		log.Printf("Allowed Auth Domain: %s", cfg.AllowedAuthDomain)
	}
	log.Printf("Swagger UI available at http://localhost%s/swagger/index.html", serverAddr)

	if err := router.Run(serverAddr); err != nil {
		log.Fatalf("Failed to run server: %v", err)
	}
}
