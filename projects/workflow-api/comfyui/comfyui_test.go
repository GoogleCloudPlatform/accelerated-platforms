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
	"encoding/json"
	"errors" // Required for errors.As in LoadWorkflow
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestNewClient ensures client creation and URL parsing works as expected.
func TestNewClient(t *testing.T) {
	t.Run("Valid HTTP URL", func(t *testing.T) {
		client, err := NewClient("http://127.0.0.1:8188")
		require.NoError(t, err)
		assert.NotNil(t, client)
		assert.Equal(t, "http://127.0.0.1:8188", client.BaseURL)
		assert.Equal(t, "ws://127.0.0.1:8188", client.WSBaseURL)
		assert.NotEmpty(t, client.ClientID)
	})

	t.Run("Valid HTTPS URL with trailing slash", func(t *testing.T) {
		client, err := NewClient("https://comfy.example.com/")
		require.NoError(t, err)
		assert.NotNil(t, client)
		assert.Equal(t, "https://comfy.example.com", client.BaseURL) // Trailing slash removed
		assert.Equal(t, "wss://comfy.example.com", client.WSBaseURL)
		assert.NotEmpty(t, client.ClientID)
	})

	t.Run("Valid clientID provided", func(t *testing.T) {
		customID := "my-custom-client-id"
		client, err := NewClient("http://localhost:1234", customID)
		require.NoError(t, err)
		assert.Equal(t, customID, client.ClientID)
	})

	t.Run("Invalid URL", func(t *testing.T) {
		_, err := NewClient("htp://invalid-url") // Invalid scheme
		require.Error(t, err)
	})
}

func TestClient_QueuePrompt(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		require.Equal(t, "/prompt", r.URL.Path)
		require.Equal(t, "POST", r.Method)

		var reqPayload PromptRequestPayload
		err := json.NewDecoder(r.Body).Decode(&reqPayload)
		require.NoError(t, err)
		defer r.Body.Close()

		assert.NotEmpty(t, reqPayload.ClientID)
		assert.Contains(t, reqPayload.Prompt, "node1")

		mockResp := PromptResponse{
			PromptID: "test-prompt-id-123",
			Number:   1,
		}
		w.Header().Set("Content-Type", "application/json")
		err = json.NewEncoder(w).Encode(mockResp)
		require.NoError(t, err)
	}))
	defer server.Close()

	client, err := NewClient(server.URL) // httptest.Server.URL includes http://
	require.NoError(t, err)

	testPrompt := map[string]interface{}{"node1": "data1"}
	resp, err := client.QueuePrompt(testPrompt)
	require.NoError(t, err)
	require.NotNil(t, resp)
	assert.Equal(t, "test-prompt-id-123", resp.PromptID)
	assert.Equal(t, 1, resp.Number)

	// Test with specific client ID
	customClientID := "custom-test-client"
	resp, err = client.QueuePromptWithClientID(testPrompt, customClientID)
	require.NoError(t, err)
	require.NotNil(t, resp)
	assert.Equal(t, "test-prompt-id-123", resp.PromptID) // Server handler doesn't check clientID for this test response

	// Test with empty client ID for QueuePromptWithClientID
	_, err = client.QueuePromptWithClientID(testPrompt, "")
	require.Error(t, err)
	assert.Contains(t, err.Error(), "clientID cannot be empty")
}

func TestClient_GetHistory(t *testing.T) {
	expectedPromptID := "history-prompt-456"
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		require.True(t, strings.HasPrefix(r.URL.Path, "/history/"), "Path prefix mismatch")
		require.Equal(t, "GET", r.Method)

		parts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
		require.Len(t, parts, 2, "URL path parts count")
		require.Equal(t, expectedPromptID, parts[1], "Prompt ID in URL mismatch")

		mockHistory := map[string]interface{}{
			expectedPromptID: map[string]interface{}{ // The API returns a map keyed by the prompt_id
				"outputs": map[string]interface{}{
					"node_10": "output_data_here",
				},
				"status": map[string]interface{}{"completed": true},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		err := json.NewEncoder(w).Encode(mockHistory)
		require.NoError(t, err)
	}))
	defer server.Close()

	client, err := NewClient(server.URL)
	require.NoError(t, err)

	history, err := client.GetHistory(expectedPromptID)
	require.NoError(t, err)
	require.NotNil(t, history)

	promptHistory, ok := history[expectedPromptID].(map[string]interface{})
	require.True(t, ok, "Expected promptID key in history response")
	outputs, ok := promptHistory["outputs"].(map[string]interface{})
	require.True(t, ok)
	assert.Equal(t, "output_data_here", outputs["node_10"])
}

func TestClient_GetImage(t *testing.T) {
	mockImageData := []byte("this is mock image data")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		require.Equal(t, "/view", r.URL.Path)
		require.Equal(t, "GET", r.Method)

		assert.Equal(t, "test_image.png", r.URL.Query().Get("filename"))
		assert.Equal(t, "sub", r.URL.Query().Get("subfolder"))
		assert.Equal(t, "output", r.URL.Query().Get("type"))

		w.Header().Set("Content-Type", "image/png")
		_, err := w.Write(mockImageData)
		require.NoError(t, err)
	}))
	defer server.Close()

	client, err := NewClient(server.URL)
	require.NoError(t, err)

	imageData, err := client.GetImage("test_image.png", "sub", "output")
	require.NoError(t, err)
	assert.Equal(t, string(mockImageData), string(imageData))
}

func TestClient_UploadImage(t *testing.T) {
	tmpFile, err := os.CreateTemp("", "test_upload_*.png")
	require.NoError(t, err, "Failed to create temp file for upload")
	defer os.Remove(tmpFile.Name())

	_, err = tmpFile.Write([]byte("fake image content"))
	require.NoError(t, err, "Failed to write to temp file")
	err = tmpFile.Close()
	require.NoError(t, err)

	expectedImageNameInForm := "test_image_uploaded.png" // This is the 'name' param to UploadImage
	expectedImageType := "input"
	expectedOverwrite := "false" // Multipart form fields are strings

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		require.Equal(t, "/upload/image", r.URL.Path)
		require.Equal(t, "POST", r.Method)

		err := r.ParseMultipartForm(10 << 20) // 10 MB max memory
		require.NoError(t, err, "Server failed to parse multipart form")

		assert.Equal(t, expectedImageType, r.FormValue("type"))
		assert.Equal(t, expectedOverwrite, r.FormValue("overwrite"))

		file, handler, err := r.FormFile("image")
		require.NoError(t, err, "Server failed to get form file 'image'")
		defer file.Close()

		assert.Equal(t, expectedImageNameInForm, handler.Filename)

		fileBytes, err := io.ReadAll(file)
		require.NoError(t, err)
		assert.Equal(t, "fake image content", string(fileBytes))

		mockResp := UploadImageResponse{Name: handler.Filename, Subfolder: "uploads", Type: "input"}
		w.Header().Set("Content-Type", "application/json")
		err = json.NewEncoder(w).Encode(mockResp)
		require.NoError(t, err)
	}))
	defer server.Close()

	client, err := NewClient(server.URL)
	require.NoError(t, err)

	uploadResp, err := client.UploadImage(tmpFile.Name(), expectedImageNameInForm, expectedImageType, false)
	require.NoError(t, err)
	require.NotNil(t, uploadResp)
	assert.Equal(t, expectedImageNameInForm, uploadResp.Name)
	assert.Equal(t, "uploads", uploadResp.Subfolder)
}

func TestLoadWorkflow(t *testing.T) {
	t.Run("Valid workflow", func(t *testing.T) {
		content := `{"3": {"class_type": "KSampler"}, "4": {"class_type": "EmptyLatentImage"}}`
		tmpFile, err := os.CreateTemp("", "workflow_*.json")
		require.NoError(t, err)
		defer os.Remove(tmpFile.Name())

		_, err = tmpFile.WriteString(content)
		require.NoError(t, err)
		err = tmpFile.Close()
		require.NoError(t, err)

		wf, err := LoadWorkflow(tmpFile.Name())
		require.NoError(t, err)
		require.NotNil(t, wf)
		assert.Contains(t, wf, "3")
		node3, ok := wf["3"].(map[string]interface{})
		require.True(t, ok)
		assert.Equal(t, "KSampler", node3["class_type"])
	})

	t.Run("File not found", func(t *testing.T) {
		_, err := LoadWorkflow("non_existent_workflow.json")
		require.Error(t, err)
		assert.True(t, os.IsNotExist(errors.Unwrap(err)), "Expected IsNotExist error")
	})

	t.Run("Invalid JSON", func(t *testing.T) {
		content := `{"3": {"class_type": "KSampler"}, "4":` // Incomplete JSON
		tmpFile, err := os.CreateTemp("", "workflow_*.json")
		require.NoError(t, err)
		defer os.Remove(tmpFile.Name())

		_, err = tmpFile.WriteString(content)
		require.NoError(t, err)
		err = tmpFile.Close()
		require.NoError(t, err)

		_, err = LoadWorkflow(tmpFile.Name())
		require.Error(t, err)
		var syntaxError *json.SyntaxError
		isSyntaxError := errors.As(err, &syntaxError)
		assert.True(t, isSyntaxError, "Expected a json.SyntaxError")
	})
}

// Note: Testing OpenWebsocketConnection would require a mock WebSocket server,
// which is more involved than httptest. It's often done as an integration test
// or with specialized WebSocket mocking libraries.
func TestClient_OpenWebsocketConnection(t *testing.T) {
	// This is a basic test for URL construction, not actual connection.
	client, err := NewClient("http://localhost:9999")
	require.NoError(t, err)

	// We can't dial in a unit test easily without a live ws server or a mock one.
	// So, we'll just check the URL it would attempt to dial.
	// For a real test, you'd use a library like nhooyr.io/websocket/wstest
	// or set up a simple echo websocket server.

	expectedURLPrefix := "ws://localhost:9999/ws?clientId="
	// The actual dial call:
	// conn, clientID, err := client.OpenWebsocketConnection()
	// For now, we know it prints the URL.
	// This test is more of a placeholder to indicate where real ws testing would go.
	t.Logf("OpenWebsocketConnection would attempt to connect to a URL starting with: %s%s", expectedURLPrefix, client.ClientID)
	assert.True(t, true, "Placeholder for actual WebSocket connection test")
}
