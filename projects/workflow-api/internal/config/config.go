package config

import (
	"fmt"
	"log"
	"os"
	"time"

	"github.com/joho/godotenv" // Optional: for loading .env file
)

type Config struct {
	ComfyUIBaseURL string
	GoogleClientID string
	// GoogleClientSecret string // Secret might not be needed for just validating access tokens
	AllowedAuthDomain string // Optional: Restrict login to a specific GSuite domain (e.g., "yourcompany.com")
	ServerPort        string
	GinMode           string // "debug" or "release"
}

func LoadConfig() *Config {
	// Load .env file if it exists (useful for local development)
	err := godotenv.Load()
	if err != nil {
		log.Println("No .env file found, reading environment variables directly")
	}

	cfg := &Config{
		ComfyUIBaseURL:    getEnv("COMFYUI_BASE_URL", "http://127.0.0.1:8188"),
		GoogleClientID:    getEnv("GOOGLE_CLIENT_ID", ""),    // Optional
		AllowedAuthDomain: getEnv("ALLOWED_AUTH_DOMAIN", ""), // Optional
		ServerPort:        getEnv("SERVER_PORT", "8080"),
		GinMode:           getEnv("GIN_MODE", "release"),
	}

	// Validate URL format (basic check)
	if cfg.ComfyUIBaseURL == "" {
		panic("COMFYUI_BASE_URL environment variable is not set")
	}

	return cfg
}

func getEnv(key, fallback string) string {
	if value, exists := os.LookupEnv(key); exists {
		return value
	}
	log.Printf("Using fallback for environment variable %s: %s", key, fallback)
	return fallback
}

func getEnvOrPanic(key string) string {
	if value, exists := os.LookupEnv(key); exists && value != "" {
		return value
	}
	panic(fmt.Sprintf("Required environment variable %s is not set", key))
}

// Helper for later if needed
func getEnvAsDuration(key string, fallback time.Duration) time.Duration {
	valueStr := getEnv(key, "")
	if valueStr == "" {
		return fallback
	}
	if duration, err := time.ParseDuration(valueStr); err == nil {
		return duration
	}
	log.Printf("Invalid duration format for %s: %s. Using fallback %v", key, valueStr, fallback)
	return fallback
}
