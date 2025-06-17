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
	"fmt"
	"log"
	"net/http"
	"os" // Make sure os is imported
	"path/filepath"
	"strings" // Make sure strings is imported

	"comfyui-api-service/comfyui" // Import your local comfyui package

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// APIHandler holds dependencies like the ComfyUI client.
type APIHandler struct {
	ComfyClient *comfyui.Client
}

// NewAPIHandler creates a new handler instance.
func NewAPIHandler(client *comfyui.Client) *APIHandler {
	return &APIHandler{
		ComfyClient: client,
	}
}

// ErrorResponse is a generic structure for API error responses.
type ErrorResponse struct {
	Error   string `json:"error" example:"A human-readable error message"`
	Details string `json:"details,omitempty" example:"Optional additional error details"`
}

// QueuePromptRequest represents the expected JSON body for queueing a prompt.
type QueuePromptRequest struct {
	Prompt map[string]interface{} `json:"prompt" binding:"required"`
}

// QueuePrompt godoc
// @Summary      Queue a generation prompt
// @Description  Sends a workflow prompt to the ComfyUI backend for processing. The prompt field is a map where keys are node IDs (strings) and values are objects defining the node's class_type and inputs. Example: `{"3": {"class_type": "KSampler", "inputs": {"seed": 123}}}`
// @Tags         ComfyUI
// @Accept       json
// @Produce      json
// @Param        prompt body QueuePromptRequest true "The prompt workflow JSON and client ID"
// @Success      200  {object} comfyui.PromptResponse "Successfully queued prompt"
// @Failure      400  {object} api.ErrorResponse "Bad Request (e.g., invalid JSON)"
// @Failure      401  {object} api.ErrorResponse "Unauthorized (Invalid or missing Bearer token)"
// @Failure      500  {object} api.ErrorResponse "Internal Server Error (e.g., ComfyUI unreachable)"
// @Security     BearerAuth
// @Router       /queue_prompt [post]
func (h *APIHandler) QueuePrompt(c *gin.Context) {
	var req QueuePromptRequest

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, ErrorResponse{Error: "Invalid request body", Details: err.Error()})
		return
	}

	resp, err := h.ComfyClient.QueuePrompt(req.Prompt)
	if err != nil {
		log.Printf("Error queueing prompt: %v", err)
		c.JSON(http.StatusInternalServerError, ErrorResponse{Error: "Failed to queue prompt", Details: err.Error()})
		return
	}
	c.JSON(http.StatusOK, resp)
}

// GetHistory godoc
// @Summary      Get prompt history
// @Description  Retrieves the execution history and outputs for a specific prompt ID.
// @Tags         ComfyUI
// @Produce      json
// @Param        prompt_id path string true "The ID of the prompt" Format(uuid) example("a1b2c3d4-e5f6-7890-1234-567890abcdef")
// @Success      200  {object} map[string]interface{} "Prompt history details"
// @Failure      400  {object} api.ErrorResponse "Bad Request (e.g., missing prompt_id)"
// @Failure      401  {object} api.ErrorResponse "Unauthorized (Invalid or missing Bearer token)"
// @Failure      404  {object} api.ErrorResponse "Not Found (Prompt ID not found in ComfyUI)"
// @Failure      500  {object} api.ErrorResponse "Internal Server Error"
// @Security     BearerAuth
// @Router       /history/{prompt_id} [get]
func (h *APIHandler) GetHistory(c *gin.Context) {
	promptID := c.Param("prompt_id")
	if promptID == "" {
		c.JSON(http.StatusBadRequest, ErrorResponse{Error: "prompt_id path parameter is required"})
		return
	}

	history, err := h.ComfyClient.GetHistory(promptID)
	if err != nil {
		log.Printf("Error getting history for prompt %s: %v", promptID, err)
		// Basic check if the error indicates not found (depends on comfyui client error wrapping)
		if strings.Contains(err.Error(), "status: 404 Not Found") || strings.Contains(err.Error(), "not found") { // Example check
			c.JSON(http.StatusNotFound, ErrorResponse{Error: "Prompt history not found", Details: fmt.Sprintf("prompt_id: %s", promptID)})
		} else {
			c.JSON(http.StatusInternalServerError, ErrorResponse{Error: "Failed to get prompt history", Details: err.Error()})
		}
		return
	}

	if history == nil || len(history) == 0 {
		c.JSON(http.StatusNotFound, ErrorResponse{Error: "Prompt history not found or empty", Details: fmt.Sprintf("prompt_id: %s", promptID)})
		return
	}
	c.JSON(http.StatusOK, history)
}

// GetImage godoc
// @Summary      Get generated image
// @Description  Downloads a specific image generated by ComfyUI.
// @Tags         ComfyUI
// @Produce      image/png
// @Produce      image/jpeg
// @Produce      image/webp
// @Produce      application/octet-stream
// @Param        filename  query string true "Filename of the image" example("ComfyUI_00001_.png")
// @Param        subfolder query string false "Subfolder containing the image (if any)" example("output")
// @Param        type      query string true "Type of image (e.g., 'output', 'input', 'temp')" example("output") Enums(output,input,temp)
// @Success      200  {file} file "The requested image file"
// @Failure      400  {object} api.ErrorResponse "Bad Request (Missing required query parameters)"
// @Failure      401  {object} api.ErrorResponse "Unauthorized"
// @Failure      404  {object} api.ErrorResponse "Not Found (Image not found on ComfyUI server)"
// @Failure      500  {object} api.ErrorResponse "Internal Server Error"
// @Security     BearerAuth
// @Router       /image [get]
func (h *APIHandler) GetImage(c *gin.Context) {
	filename := c.Query("filename")
	folderType := c.Query("type")
	subfolder := c.Query("subfolder")

	if filename == "" || folderType == "" {
		c.JSON(http.StatusBadRequest, ErrorResponse{Error: "Missing required query parameters: filename, type"})
		return
	}

	imageData, err := h.ComfyClient.GetImage(filename, subfolder, folderType)
	if err != nil {
		log.Printf("Error getting image '%s': %v", filename, err)
		if strings.Contains(err.Error(), "status: 404 Not Found") || strings.Contains(err.Error(), "not found") {
			c.JSON(http.StatusNotFound, ErrorResponse{Error: "Image not found"})
		} else {
			c.JSON(http.StatusInternalServerError, ErrorResponse{Error: "Failed to get image", Details: err.Error()})
		}
		return
	}

	contentType := "application/octet-stream"
	ext := strings.ToLower(filepath.Ext(filename))
	switch ext {
	case ".png":
		contentType = "image/png"
	case ".jpg", ".jpeg":
		contentType = "image/jpeg"
	case ".webp":
		contentType = "image/webp"
	}
	c.Data(http.StatusOK, contentType, imageData)
}

// UploadImage godoc
// @Summary      Upload an image
// @Description  Uploads an image file to the ComfyUI input directory.
// @Tags         ComfyUI
// @Accept       multipart/form-data
// @Produce      json
// @Param        image      formData file   true  "Image file to upload"
// @Param        type       formData string true  "Type of upload (usually 'input')" example("input") Enums(input,temp)
// @Param        overwrite  formData bool   false "Overwrite existing file (default: false)" example(false)
// @Success      200 {object} comfyui.UploadImageResponse "Image uploaded successfully"
// @Failure      400 {object} api.ErrorResponse "Bad Request (e.g., missing file or type)"
// @Failure      401 {object} api.ErrorResponse "Unauthorized"
// @Failure      500 {object} api.ErrorResponse "Internal Server Error (e.g., upload failed)"
// @Security     BearerAuth
// @Router       /upload_image [post]
func (h *APIHandler) UploadImage(c *gin.Context) {
	imageType := c.PostForm("type")
	overwriteStr := c.PostForm("overwrite")
	overwrite := overwriteStr == "true"

	if imageType == "" {
		c.JSON(http.StatusBadRequest, ErrorResponse{Error: "Form field 'type' is required"})
		return
	}

	fileHeader, err := c.FormFile("image")
	if err != nil {
		c.JSON(http.StatusBadRequest, ErrorResponse{Error: "Form field 'image' (file) is required", Details: err.Error()})
		return
	}

	tmpFileName := filepath.Join(os.TempDir(), fmt.Sprintf("upload_%s_%s", uuid.NewString(), fileHeader.Filename))
	if err := c.SaveUploadedFile(fileHeader, tmpFileName); err != nil {
		log.Printf("Error saving temporary upload file: %v", err)
		c.JSON(http.StatusInternalServerError, ErrorResponse{Error: "Failed to process uploaded file", Details: err.Error()})
		return
	}
	defer func() {
		if err := os.Remove(tmpFileName); err != nil {
			log.Printf("Warning: failed to remove temporary upload file %s: %v", tmpFileName, err)
		}
	}()

	uploadResp, err := h.ComfyClient.UploadImage(tmpFileName, fileHeader.Filename, imageType, overwrite)
	if err != nil {
		log.Printf("Error uploading image to ComfyUI: %v", err)
		c.JSON(http.StatusInternalServerError, ErrorResponse{Error: "Failed to upload image", Details: err.Error()})
		return
	}
	c.JSON(http.StatusOK, uploadResp)
}
