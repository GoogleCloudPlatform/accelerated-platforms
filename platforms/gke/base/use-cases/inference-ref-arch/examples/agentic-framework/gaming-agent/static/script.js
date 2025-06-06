document.addEventListener('DOMContentLoaded', () => {
    // --- Add these constants from your Python config.py ---
    const NUM_IMAGES_TO_GENERATE = 4; // Matches config.NUM_IMAGES_TO_GENERATE in Python
    const NUM_VIDEOS_PER_IMAGE = 2;   // Matches config.NUM_VIDEOS_PER_CALL in Python
    // ---------------------------------------------------

    const promptInput = document.getElementById('promptInput');
    const sendPromptBtn = document.getElementById('sendPrompt');
    const messagesDiv = document.getElementById('messages');
    const dialogueSelectionDiv = document.getElementById('dialogueSelection');
    const dialogueOptionsDiv = document.getElementById('dialogueOptions');

    const generatedContentDiv = document.getElementById('generatedContent');
    const imagesContainer = document.getElementById('imagesContainer');
    const videosContainer = document.getElementById('videosContainer');

    // --- Manage rootLogId on frontend ---
    let sessionId = localStorage.getItem('agentSessionId') || null;
    let rootLogId = localStorage.getItem('rootLogId') || generateUUID(); // Generate or retrieve
    localStorage.setItem('rootLogId', rootLogId); // Store for future sessions (optional, but good for demo)

    console.log("INIT DEBUG: DOM Content Loaded.");
    console.log("INIT DEBUG: Initial Session ID:", sessionId);
    console.log("INIT DEBUG: Initial Root Log ID:", rootLogId);

    // Helper to add messages to the chat display
    function addMessage(text, sender) {
        console.log(`ADD MESSAGE DEBUG: Adding message - Sender: ${sender}, Text: ${text.substring(0, Math.min(text.length, 50))}...`);
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', sender);
        messageElement.innerHTML = text.replace(/\n/g, '<br>');
        messagesDiv.appendChild(messageElement);
        setTimeout(() => {
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            console.log("ADD MESSAGE DEBUG: Scrolled messages div to bottom.");
        }, 0);
    }

    // Function to generate a simple UUID-like string for log_id
    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0,
                v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    // Function to display loading state
    function showLoading(message) {
        console.log(`SHOW LOADING DEBUG: Displaying loading state with message: ${message.substring(0, Math.min(message.length, 50))}...`);
        promptInput.value = '';
        promptInput.placeholder = 'Agent is thinking...';
        promptInput.disabled = true;
        sendPromptBtn.disabled = true;

        if (!document.getElementById('loadingMessageInChat')) {
            const loadingMessageElement = document.createElement('div');
            loadingMessageElement.id = 'loadingMessageInChat';
            loadingMessageElement.classList.add('message', 'system', 'loading');
            loadingMessageElement.innerHTML = `<span class="spinner"></span> ${message}`;
            messagesDiv.appendChild(loadingMessageElement);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        } else {
            document.getElementById('loadingMessageInChat').innerHTML = `<span class="spinner"></span> ${message}`;
        }

        dialogueSelectionDiv.classList.add('hidden');
        generatedContentDiv.classList.add('hidden');
        promptInput.parentElement.classList.add('hidden');
        console.log("SHOW LOADING DEBUG: Hidden dialogue, generated content, and prompt input.");
    }

    // Function to hide loading state
    function hideLoading() {
        console.log("HIDE LOADING DEBUG: Hiding loading state.");
        sendPromptBtn.disabled = false;
        promptInput.disabled = false;
        promptInput.value = '';
        promptInput.placeholder = 'Type your prompt here...';
        promptInput.focus();

        const loadingMessageElement = document.getElementById('loadingSpinner');
        if (loadingMessageElement) {
            loadingMessageElement.remove();
            console.log("HIDE LOADING DEBUG: Removed #loadingSpinner.");
        } else {
            const loadingMessageInChat = document.getElementById('loadingMessageInChat');
            if (loadingMessageInChat) {
                loadingMessageInChat.remove();
                console.log("HIDE LOADING DEBUG: Removed #loadingMessageInChat.");
            }
        }
        console.log("HIDE LOADING DEBUG: Prompt input re-enabled and focused.");
    }

    // Function to call the FastAPI agent for initial prompt or content generation
    async function callAgent(rawPrompt, isContentGeneration = false) {
        console.log(`CALL AGENT DEBUG: Function called. Raw Prompt: ${rawPrompt.substring(0, Math.min(rawPrompt.length, 50))}..., Is Content Gen: ${isContentGeneration}`);
        const fullPrompt = `[ROOT_LOG_ID:${rootLogId}] ${rawPrompt}`;

        if (!isContentGeneration) {
            addMessage(rawPrompt, 'user');
        }
        showLoading(`Processing your request: "${rawPrompt.substring(0, Math.min(rawPrompt.length, 50))}..."`);

        const data = {
            prompt: fullPrompt,
            session_id: sessionId,
            is_content_generation: isContentGeneration
        };
        console.log("CALL AGENT DEBUG: Request payload:", data);

        try {
            const response = await fetch('/ask_agent', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            });
            console.log("CALL AGENT DEBUG: Fetch response received. Status:", response.status);

            if (!response.ok) {
                const errorData = await response.json();
                console.error("CALL AGENT ERROR: Backend returned non-OK response. Status:", response.status, "Error Data:", errorData);
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log("CALL AGENT DEBUG: Backend response 'result' (parsed JSON):", result);

            let finalImageUrls = [];
            let finalVideoUrls = [];
            let foundDialogue = false; // This flag dictates UI state after response

            if (result.response_text) {
                const cleanedResponseText = result.response_text.replace(/\[ROOT_LOG_ID:[a-f0-9-]+\]\s*/, '');
                if (cleanedResponseText.trim()) {
                    addMessage(cleanedResponseText, 'agent');
                } else {
                    console.log("CALL AGENT DEBUG: Cleaned response text was empty, not added to chat.");
                }
            } else {
                console.log("CALL AGENT DEBUG: No 'response_text' in backend result.");
            }

            if (result.tool_outputs) {
                const toolOutputs = result.tool_outputs;
                console.log("CALL AGENT DEBUG: toolOutputs received:", JSON.stringify(toolOutputs, null, 2));

                // 1. Try to extract dialogue options first
                let dialogueOptions = [];
                // Check if it's a single tool_output object
                if (toolOutputs.tool_output && toolOutputs.tool_output.result && Array.isArray(toolOutputs.tool_output.result)) {
                    // FIX: Use actual tool name
                    if (toolOutputs.tool_name === 'generate_and_log_npc_dialogue_tool') {
                         dialogueOptions = toolOutputs.tool_output.result;
                         console.log("CALL AGENT DEBUG: Extracted dialogue from single 'tool_output.result':", dialogueOptions);
                    } else {
                         console.log("CALL AGENT DEBUG: Single 'tool_output' found but not a dialogue tool.");
                    }
                }
                // Check if it's an 'all_tool_outputs' array
                else if (toolOutputs.all_tool_outputs && Array.isArray(toolOutputs.all_tool_outputs)) {
                    console.log("CALL AGENT DEBUG: Processing 'all_tool_outputs' array.");
                    const dialogueToolOutput = toolOutputs.all_tool_outputs.find(
                        output => {
                            console.log("CALL AGENT DEBUG: Checking tool_name:", output.tool_name);
                            // FIX: Use actual tool name
                            return output.tool_name === 'generate_and_log_npc_dialogue_tool' &&
                                   output.tool_output && output.tool_output.result && Array.isArray(output.tool_output.result);
                        }
                    );
                    if (dialogueToolOutput) {
                        dialogueOptions = dialogueToolOutput.tool_output.result;
                        console.log("CALL AGENT DEBUG: Extracted dialogue from 'all_tool_outputs' (generate_and_log_npc_dialogue_tool):", dialogueOptions);
                    } else {
                        console.log("CALL AGENT DEBUG: 'generate_and_log_npc_dialogue_tool' not found in 'all_tool_outputs' or its structure is incorrect.");
                    }
                } else {
                    console.log("CALL AGENT DEBUG: 'tool_outputs' structure is neither single 'tool_output' nor 'all_tool_outputs' array.");
                }

                console.log("CALL AGENT DEBUG: Final dialogueOptions length after extraction attempt:", dialogueOptions.length);

                if (dialogueOptions.length > 0) {
                    displayDialogueSelection(dialogueOptions); // This function makes dialogueSelectionDiv visible
                    foundDialogue = true;
                    console.log("CALL AGENT DEBUG: Dialogue options found. foundDialogue set to TRUE. displayDialogueSelection called.");
                } else {
                    console.log("CALL AGENT DEBUG: No dialogue options found. Proceeding to check for images/videos.");

                    if (toolOutputs.all_tool_outputs && Array.isArray(toolOutputs.all_tool_outputs)) {
                        console.log("CALL AGENT DEBUG: Processing tool_outputs for images and videos from 'all_tool_outputs'.");
                        toolOutputs.all_tool_outputs.forEach(output => {
                            // FIX: Use actual tool names for images and video orchestration
                            if (output.tool_name === 'generate_and_log_images_tool' && output.tool_output && Array.isArray(output.tool_output.result)) {
                                finalImageUrls.push(...output.tool_output.result);
                                console.log("CALL AGENT DEBUG: Collected images:", output.tool_output.result);
                            } else if (output.tool_name === 'wrapped_orchestrate_video_generation_tool' && output.tool_output && Array.isArray(output.tool_output.result)) {
                                finalVideoUrls.push(...output.tool_output.result);
                                console.log("CALL AGENT DEBUG: Collected orchestrated videos:", output.tool_output.result);
                            }
                            // Fallback for individual video tool if it shows up (should be rare with orchestration)
                            else if (output.tool_name === 'generate_and_log_video_tool' && output.tool_output) {
                                if (Array.isArray(output.tool_output)) {
                                    finalVideoUrls.push(...output.tool_output);
                                } else if (typeof output.tool_output === 'string') {
                                    finalVideoUrls.push(output.tool_output);
                                }
                                console.log("CALL AGENT DEBUG: Collected individual videos (fallback):", output.tool_output);
                            }
                        });
                    } else if (toolOutputs.tool_output && toolOutputs.tool_output.result) {
                        // Fallback for single tool_output if it's image or video
                        // FIX: Use actual tool names here too
                        if (toolOutputs.tool_name === 'generate_and_log_images_tool' && Array.isArray(toolOutputs.tool_output.result)) {
                            finalImageUrls.push(...toolOutputs.tool_output.result);
                            console.log("CALL AGENT DEBUG: Collected images from single tool_output:", toolOutputs.tool_output.result);
                        } else if (toolOutputs.tool_name === 'wrapped_orchestrate_video_generation_tool' && Array.isArray(toolOutputs.tool_output.result)) {
                            finalVideoUrls.push(...toolOutputs.tool_output.result);
                             console.log("CALL AGENT DEBUG: Collected orchestrated videos from single tool_output:", toolOutputs.tool_output.result);
                        }
                    }

                    finalImageUrls = [...new Set(finalImageUrls)];
                    finalVideoUrls = [...new Set(finalVideoUrls)];
                    console.log("CALL AGENT DEBUG: Final unique image URLs:", finalImageUrls.length);
                    console.log("CALL AGENT DEBUG: Final unique video URLs:", finalVideoUrls.length);

                    if (finalImageUrls.length > 0 || finalVideoUrls.length > 0) {
                        displayGeneratedContent(finalImageUrls, finalVideoUrls);
                        console.log("CALL AGENT DEBUG: Generated content (images/videos) found and displayGeneratedContent called.");
                    } else {
                        console.log("CALL AGENT DEBUG: No images or videos found in tool outputs.");
                    }
                }
            } else {
                console.log("CALL AGENT DEBUG: No 'tool_outputs' property in backend result.");
            }

            // --- CRITICAL UI STATE MANAGEMENT ---
            console.log("CALL AGENT DEBUG: Entering UI state management. foundDialogue:", foundDialogue);
            if (foundDialogue) {
                promptInput.parentElement.classList.add('hidden');
                dialogueSelectionDiv.classList.remove('hidden');
                console.log("CALL AGENT DEBUG: UI State: Prompt input hidden, Dialogue selection shown.");
            } else {
                promptInput.parentElement.classList.remove('hidden');
                dialogueSelectionDiv.classList.add('hidden');
                console.log("CALL AGENT DEBUG: UI State: Prompt input shown, Dialogue selection hidden.");
                if (finalImageUrls.length === 0 && finalVideoUrls.length === 0) {
                    generatedContentDiv.classList.add('hidden');
                    console.log("CALL AGENT DEBUG: UI State: Hiding generated content as no new assets were found.");
                }
            }


        } catch (error) {
            console.error('CALL AGENT ERROR: Caught an error in try-catch block:', error);
            addMessage(`Error: ${error.message}. Please try again.`, 'system');

            promptInput.parentElement.classList.remove('hidden');
            dialogueSelectionDiv.classList.add('hidden');
            generatedContentDiv.classList.add('hidden');
            console.log("CALL AGENT ERROR: UI State: Prompt input shown, others hidden due to error.");
        } finally {
            hideLoading();
            console.log("CALL AGENT DEBUG: Finally block executed. Loading state hidden.");
        }
    }

    // Function to display dialogue options for selection
    function displayDialogueSelection(options) {
        console.log("DISPLAY DIALOGUE SELECTION DEBUG: Function called. Options received:", options);
        dialogueOptionsDiv.innerHTML = '';
        options.forEach((option, index) => {
            const optionDiv = document.createElement('div');
            optionDiv.classList.add('dialogue-option');
            optionDiv.innerHTML = `<span>${index + 1}.</span> ${option}`;
            optionDiv.dataset.dialogueText = option;

            optionDiv.addEventListener('click', () => {
                console.log("DISPLAY DIALOGUE SELECTION DEBUG: Dialogue option clicked:", option);
                document.querySelectorAll('.dialogue-option').forEach(el => el.classList.remove('selected'));
                optionDiv.classList.add('selected');

                addMessage(`Selected dialogue: "${option}"`, 'user');

                const contentGenPrompt = `Orchestrate generation of ${NUM_IMAGES_TO_GENERATE} images and then ${NUM_VIDEOS_PER_IMAGE} videos per image, based on the following dialogue: "${option}".`;
                console.log("DISPLAY DIALOGUE SELECTION DEBUG: Calling callAgent for content generation with prompt:", contentGenPrompt.substring(0, Math.min(contentGenPrompt.length, 50)));

                callAgent(contentGenPrompt, true);

                dialogueSelectionDiv.classList.add('hidden'); // Hide dialogue selection immediately on click
                console.log("DISPLAY DIALOGUE SELECTION DEBUG: Dialogue selection hidden after click.");
            });
            dialogueOptionsDiv.appendChild(optionDiv);
        });
        dialogueSelectionDiv.classList.remove('hidden'); // This is the key line to make it visible initially
        console.log("DISPLAY DIALOGUE SELECTION DEBUG: dialogueSelectionDiv set to visible.");
    }

    // Function to display generated images and videos
    function displayGeneratedContent(imageUrls, videoUrls) {
        console.log("DISPLAY GENERATED CONTENT DEBUG: Function called. Image URLs count:", imageUrls.length, "Video URLs count:", videoUrls.length);
        imagesContainer.innerHTML = '';
        videosContainer.innerHTML = '';

        if (imageUrls.length > 0) {
            console.log("DISPLAY GENERATED CONTENT DEBUG: Populating images.");
            imageUrls.forEach(url => {
                const div = document.createElement('div');
                div.classList.add('asset-item');
                const img = document.createElement('img');
                img.src = url;
                img.alt = "Generated Image";
                img.onerror = (e) => {
                    console.error("DISPLAY GENERATED CONTENT ERROR: Image failed to load:", url, e);
                    img.src = '';
                    img.alt = 'Image failed to load.';
                    img.style.border = '1px dashed grey';
                    img.style.minHeight = '100px';
                    img.style.backgroundColor = '#333';
                    img.style.color = '#ccc';
                    img.style.display = 'flex';
                    img.style.alignItems = 'center';
                    img.style.justifyContent = 'center';
                    img.textContent = 'Image failed to load.';
                };
                div.appendChild(img);
                imagesContainer.appendChild(div);
            });
            imagesContainer.parentElement.classList.remove('hidden');
        } else {
            imagesContainer.parentElement.classList.add('hidden');
            console.log("DISPLAY GENERATED CONTENT DEBUG: No images to display, hiding image container.");
        }

        if (videoUrls.length > 0) {
            console.log("DISPLAY GENERATED CONTENT DEBUG: Populating videos.");
            videoUrls.forEach(url => {
                const div = document.createElement('div');
                div.classList.add('asset-item');
                const video = document.createElement('video');
                video.controls = true;
                video.src = url;
                video.type = "video/mp4";
                video.onerror = (e) => {
                    console.error("DISPLAY GENERATED CONTENT ERROR: Video failed to load:", url, e);
                    video.src = '';
                    video.alt = 'Video failed to load.';
                    video.style.border = '1px dashed grey';
                    video.style.minHeight = '100px';
                    video.style.backgroundColor = '#333';
                    video.style.color = '#ccc';
                    video.style.display = 'flex';
                    video.style.alignItems = 'center';
                    video.style.justifyContent = 'center';
                    video.textContent = 'Video failed to load.';
                };
                div.appendChild(video);
                videosContainer.appendChild(div);
            });
            videosContainer.parentElement.classList.remove('hidden');
        } else {
            videosContainer.parentElement.classList.add('hidden');
            console.log("DISPLAY GENERATED CONTENT DEBUG: No videos to display, hiding video container.");
        }

        generatedContentDiv.classList.remove('hidden');
        dialogueSelectionDiv.classList.add('hidden'); // Keep dialogueSelection hidden if content is shown
        console.log("DISPLAY GENERATED CONTENT DEBUG: Generated content section shown, dialogue selection hidden.");
    }

    // Event Listeners
    sendPromptBtn.addEventListener('click', () => {
        const prompt = promptInput.value.trim();
        if (prompt) {
            console.log("EVENT: Send Prompt button clicked.");
            callAgent(prompt, false); // Initial prompt
        } else {
            console.log("EVENT: Send Prompt button clicked, but prompt is empty.");
        }
    });

    promptInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            console.log("EVENT: Enter key pressed in prompt input (no Shift). Triggering Send Prompt.");
            sendPromptBtn.click();
        } else if (e.key === 'Enter' && e.shiftKey) {
            console.log("EVENT: Shift+Enter pressed. Allowing new line.");
        }
    });

    // Initial state setup: Ensure correct visibility when page loads
    console.log("INIT DEBUG: Initializing UI state.");
    hideLoading(); // This just hides the spinner initially
    promptInput.parentElement.classList.remove('hidden'); // Ensure input is visible
    dialogueSelectionDiv.classList.add('hidden'); // Hidden initially
    generatedContentDiv.classList.add('hidden'); // Hidden initially
    console.log("INIT DEBUG: UI initialized: Prompt input visible, Dialogue/Content hidden.");
});
