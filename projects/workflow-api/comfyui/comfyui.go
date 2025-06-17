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

package comfyui

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/google/uuid"       // For generating client_id
	"github.com/gorilla/websocket" // A popular WebSocket library for Go
)

// Client holds the necessary configuration for interacting with the ComfyUI API.
type Client struct {
	BaseURL    string // e.g., "http://127.0.0.1:8188"
	WSBaseURL  string // e.g., "ws://127.0.0.1:8188"
	HTTPClient *http.Client
	ClientID   string // Can be set once per client or generated per connection
}

// NewClient creates a new ComfyUI API client.
// baseURL should be in the format "http://hostname:port" or "https://hostname:port".
func NewClient(baseURL string, clientID ...string) (*Client, error) {
	httpURL, err := url.Parse(baseURL)
	if err != nil {
		return nil, fmt.Errorf("invalid base URL: %w", err)
	}

	wsScheme := "ws"
	if httpURL.Scheme == "https" {
		wsScheme = "wss"
	}
	wsBaseURL := fmt.Sprintf("%s://%s", wsScheme, httpURL.Host)

	var currentClientID string
	if len(clientID) > 0 && clientID[0] != "" {
		currentClientID = clientID[0]
	} else {
		currentClientID = uuid.New().String()
	}

	return &Client{
		BaseURL:   strings.TrimRight(baseURL, "/"),
		WSBaseURL: wsBaseURL,
		HTTPClient: &http.Client{
			Timeout: 60 * time.Second, // Default timeout
		},
		ClientID: currentClientID,
	}, nil
}

// SetTimeout allows customizing the HTTP client timeout.
func (c *Client) SetTimeout(timeout time.Duration) {
	c.HTTPClient.Timeout = timeout
}

// OpenWebsocketConnection establishes a WebSocket connection to the ComfyUI server.
// It uses the client's pre-configured ClientID.
func (c *Client) OpenWebsocketConnection() (*websocket.Conn, error) {
	u := fmt.Sprintf("%s/ws?clientId=%s", c.WSBaseURL, c.ClientID)
	fmt.Printf("Connecting to WebSocket: %s\n", u)

	conn, _, err := websocket.DefaultDialer.Dial(u, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to websocket: %w", err)
	}
	return conn, nil
}

// OpenWebsocketConnectionWithNewClientID establishes a WebSocket connection with a new, unique client ID.
func (c *Client) OpenWebsocketConnectionWithNewClientID() (*websocket.Conn, string, error) {
	newClientID := uuid.New().String()
	u := fmt.Sprintf("%s/ws?clientId=%s", c.WSBaseURL, newClientID)
	fmt.Printf("Connecting to WebSocket: %s with new ClientID: %s\n", u, newClientID)

	conn, _, err := websocket.DefaultDialer.Dial(u, nil)
	if err != nil {
		return nil, "", fmt.Errorf("failed to connect to websocket: %w", err)
	}
	return conn, newClientID, nil
}

// PromptRequestPayload defines the structure for the prompt request.
type PromptRequestPayload struct {
	Prompt   map[string]interface{} `json:"prompt"`
	ClientID string                 `json:"client_id"`
}

// PromptResponse defines the structure for the prompt response.
type PromptResponse struct {
	PromptID   string                 `json:"prompt_id"`
	Number     int                    `json:"number"`
	NodeErrors map[string]interface{} `json:"node_errors,omitempty"` // Use omitempty if it can be absent
}

// QueuePrompt sends a prompt to the ComfyUI server using the client's ClientID.
func (c *Client) QueuePrompt(prompt map[string]interface{}) (*PromptResponse, error) {
	return c.QueuePromptWithClientID(prompt, c.ClientID)
}

// QueuePromptWithClientID sends a prompt to the ComfyUI server with a specific clientID.
func (c *Client) QueuePromptWithClientID(prompt map[string]interface{}, clientID string) (*PromptResponse, error) {
	if clientID == "" {
		return nil, fmt.Errorf("clientID cannot be empty")
	}
	payload := PromptRequestPayload{
		Prompt:   prompt,
		ClientID: clientID,
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal prompt payload: %w", err)
	}

	requestURL := fmt.Sprintf("%s/prompt", c.BaseURL)
	req, err := http.NewRequest("POST", requestURL, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create new HTTP request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to execute HTTP request to %s: %w", requestURL, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("failed to queue prompt, status: %s, url: %s, body: %s", resp.Status, requestURL, string(bodyBytes))
	}

	var promptResponse PromptResponse
	if err := json.NewDecoder(resp.Body).Decode(&promptResponse); err != nil {
		return nil, fmt.Errorf("failed to decode prompt response: %w", err)
	}

	return &promptResponse, nil
}

// GetHistory retrieves the history for a given prompt ID.
// The response is a map where the key is the prompt_id.
func (c *Client) GetHistory(promptID string) (map[string]interface{}, error) {
	requestURL := fmt.Sprintf("%s/history/%s", c.BaseURL, promptID)
	resp, err := c.HTTPClient.Get(requestURL)
	if err != nil {
		return nil, fmt.Errorf("failed to get history from %s: %w", requestURL, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("failed to get history, status: %s, url: %s, body: %s", resp.Status, requestURL, string(bodyBytes))
	}

	var history map[string]interface{} // The top-level response is a map keyed by prompt_id
	if err := json.NewDecoder(resp.Body).Decode(&history); err != nil {
		return nil, fmt.Errorf("failed to decode history response: %w", err)
	}
	return history, nil
}

// GetImage retrieves an image from the ComfyUI server.
func (c *Client) GetImage(filename, subfolder, folderType string) ([]byte, error) {
	data := url.Values{}
	data.Set("filename", filename)
	data.Set("subfolder", subfolder)
	data.Set("type", folderType)

	requestURL := fmt.Sprintf("%s/view?%s", c.BaseURL, data.Encode())
	resp, err := c.HTTPClient.Get(requestURL)
	if err != nil {
		return nil, fmt.Errorf("failed to get image from %s: %w", requestURL, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("failed to get image, status: %s, url: %s, body: %s", resp.Status, requestURL, string(bodyBytes))
	}

	imageData, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read image data: %w", err)
	}
	return imageData, nil
}

// UploadImageResponse defines the structure for the image upload response.
type UploadImageResponse struct {
	Name      string `json:"name"`
	Subfolder string `json:"subfolder,omitempty"`
	Type      string `json:"type,omitempty"`
}

// UploadImage uploads an image to the ComfyUI server.
func (c *Client) UploadImage(inputPath, name, imageType string, overwrite bool) (*UploadImageResponse, error) {
	file, err := os.Open(inputPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open image file '%s': %w", inputPath, err)
	}
	defer file.Close()

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	part, err := writer.CreateFormFile("image", name)
	if err != nil {
		return nil, fmt.Errorf("failed to create form file: %w", err)
	}
	_, err = io.Copy(part, file)
	if err != nil {
		return nil, fmt.Errorf("failed to copy file to form: %w", err)
	}

	_ = writer.WriteField("type", imageType)
	_ = writer.WriteField("overwrite", fmt.Sprintf("%t", overwrite)) // Booleans as strings "true" or "false"

	err = writer.Close() // This finalizes the multipart body and writes the boundary.
	if err != nil {
		return nil, fmt.Errorf("failed to close multipart writer: %w", err)
	}

	requestURL := fmt.Sprintf("%s/upload/image", c.BaseURL)
	req, err := http.NewRequest("POST", requestURL, body)
	if err != nil {
		return nil, fmt.Errorf("failed to create upload request: %w", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to execute upload request to %s: %w", requestURL, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("failed to upload image, status: %s, url: %s, body: %s", resp.Status, requestURL, string(bodyBytes))
	}

	var uploadResp UploadImageResponse
	if err := json.NewDecoder(resp.Body).Decode(&uploadResp); err != nil {
		return nil, fmt.Errorf("failed to decode upload image response: %w", err)
	}

	return &uploadResp, nil
}

// Workflow represents the structure of a ComfyUI workflow.
type Workflow map[string]interface{}

// LoadWorkflow loads a ComfyUI workflow from a JSON file.
// This is a utility function and doesn't require the API client.
func LoadWorkflow(workflowPath string) (Workflow, error) {
	fileData, err := os.ReadFile(workflowPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read workflow file %s: %w", workflowPath, err)
	}

	var workflow Workflow
	err = json.Unmarshal(fileData, &workflow)
	if err != nil {
		// Attempt to provide more context on JSON error
		var syntaxError *json.SyntaxError
		if errors.As(err, &syntaxError) {
			return nil, fmt.Errorf("failed to unmarshal workflow JSON from %s: syntax error at offset %d: %w", workflowPath, syntaxError.Offset, err)
		}
		return nil, fmt.Errorf("failed to unmarshal workflow JSON from %s: %w", workflowPath, err)
	}
	return workflow, nil
}

// --- Placeholder for more complex functions like TrackProgress ---
// type WebsocketMessage struct {
// 	Type string      `json:"type"`
// 	Data interface{} `json:"data"`
// }
//
// func (c *Client) TrackProgress(conn *websocket.Conn, promptID string, expectedNodeCount int) error {
// ... implementation ...
// }
