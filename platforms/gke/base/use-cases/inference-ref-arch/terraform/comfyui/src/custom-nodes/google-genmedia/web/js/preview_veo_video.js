
/** 
* Copyright 2025 Google LLC
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*      http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*/


// This is a preview version of veo custom node

import { app } from "../../../scripts/app.js";

/**
 * Manages a single video preview widget for a given component, with navigation for multiple videos.
 * @param {object} targetComponent The component to which the video preview will be added.
 * @param {Array<Array<string>>} videoDataArray An array of arrays, where each inner array is [filename, category].
 * @param {boolean} shouldAutoplay Whether the video should autoplay initially.
 * @param {boolean} shouldMute Whether the video should be muted.
 * @param {boolean} shouldLoop Whether the video should loop (applies to the currently playing video).
 */
function initializeSingleVideoPreviewWithNavigation(targetComponent, videoDataArray, shouldAutoplay, shouldMute, shouldLoop) {
    let previewWidget = targetComponent._mediaPreviewWidget;

    // Create the video preview widget if it doesn't already exist
    if (!previewWidget) {
        const widgetContainer = document.createElement("div");
        const hostNode = targetComponent;

        // Add the DOM widget to the component
        previewWidget = targetComponent.addDOMWidget("media_preview", "videoOutput", widgetContainer, {
            serialize: false,
            hideOnZoom: false,
            getValue() {
                return widgetContainer.value;
            },
            setValue(val) {
                widgetContainer.value = val;
            },
        });

        // Store video URLs and current index
        previewWidget.videoUrls = [];
        previewWidget.currentVideoIndex = 0;

        // Define how the widget calculates its display size
        previewWidget.computeSize = function(width) {
            if (this.mediaAspectRatio && !this.domElementWrapper.hidden) {
                // Ensure there's space for video + controls
                let calculatedHeight = (hostNode.size[0] - 20) / this.mediaAspectRatio + 10;
                // Add some extra height for the controls (buttons, text)
                calculatedHeight += 40; // Roughly 30px for controls + 10px padding
                return [width, calculatedHeight > 0 ? calculatedHeight : 0];
            }
            return [width, -4]; // Default hidden state size
        };

        // Initialize widget properties
        previewWidget.value = { hidden: false, paused: false, parameters: {} };
        previewWidget.domElementWrapper = document.createElement("div");
        previewWidget.domElementWrapper.className = "comfy_single_video_preview";
        previewWidget.domElementWrapper.style.width = "100%";
        widgetContainer.appendChild(previewWidget.domElementWrapper);

        // Create the actual video element
        previewWidget.mediaElement = document.createElement("video");
        previewWidget.mediaElement.controls = true;
        previewWidget.mediaElement.style.width = "100%";
        previewWidget.mediaElement.style.display = "block"; // Ensure it takes its own line

        // Create controls container
        previewWidget.controlsContainer = document.createElement("div");
        previewWidget.controlsContainer.style.display = "flex";
        previewWidget.controlsContainer.style.justifyContent = "space-between";
        previewWidget.controlsContainer.style.alignItems = "center";
        previewWidget.controlsContainer.style.marginTop = "10px";

        // Previous button
        previewWidget.prevButton = document.createElement("button");
        previewWidget.prevButton.textContent = "Previous";
        previewWidget.prevButton.onclick = () => navigateVideo(-1);
        previewWidget.controlsContainer.appendChild(previewWidget.prevButton);

        // Current video index text
        previewWidget.videoIndexText = document.createElement("span");
        previewWidget.videoIndexText.textContent = "0/0"; // Placeholder
        previewWidget.controlsContainer.appendChild(previewWidget.videoIndexText);

        // Next button
        previewWidget.nextButton = document.createElement("button");
        previewWidget.nextButton.textContent = "Next";
        previewWidget.nextButton.onclick = () => navigateVideo(1);
        previewWidget.controlsContainer.appendChild(previewWidget.nextButton);

        // Update aspect ratio when video metadata is loaded
        previewWidget.mediaElement.addEventListener("loadedmetadata", () => {
            previewWidget.mediaAspectRatio = previewWidget.mediaElement.videoWidth / previewWidget.mediaElement.videoHeight;
            recalculateComponentSize(targetComponent);
        });

        // Hide the video container on error
        previewWidget.mediaElement.addEventListener("error", () => {
            console.error(`Error loading video: ${previewWidget.mediaElement.src}`);
            previewWidget.mediaElement.style.display = 'none'; // Hide video on error
            previewWidget.controlsContainer.style.display = 'none'; // Hide controls too
            recalculateComponentSize(targetComponent);
        });

        previewWidget.domElementWrapper.appendChild(previewWidget.mediaElement);
        previewWidget.domElementWrapper.appendChild(previewWidget.controlsContainer);
        previewWidget.domElementWrapper.hidden = previewWidget.value.hidden;

        targetComponent._mediaPreviewWidget = previewWidget; // Cache the widget for subsequent use

        // Helper function for navigation
        const navigateVideo = (direction) => {
            previewWidget.currentVideoIndex += direction;
            if (previewWidget.currentVideoIndex < 0) {
                previewWidget.currentVideoIndex = previewWidget.videoUrls.length - 1;
            } else if (previewWidget.currentVideoIndex >= previewWidget.videoUrls.length) {
                previewWidget.currentVideoIndex = 0;
            }
            updateVideoSource();
        };

        // Helper function to update the video source and UI
        const updateVideoSource = () => {
            if (previewWidget.videoUrls.length === 0) {
                previewWidget.mediaElement.src = '';
                previewWidget.mediaElement.style.display = 'none';
                previewWidget.controlsContainer.style.display = 'none';
                previewWidget.videoIndexText.textContent = "0/0";
                return;
            }

            const currentUrl = previewWidget.videoUrls[previewWidget.currentVideoIndex];
            previewWidget.mediaElement.src = currentUrl;
            previewWidget.mediaElement.muted = shouldMute;
            // Autoplay only if it's the initial load or a new video is explicitly loaded
            // We prevent autoplay on subsequent navigation if the user paused it
            previewWidget.mediaElement.autoplay = shouldAutoplay && !previewWidget.value.paused && !previewWidget.value.hidden;
            previewWidget.mediaElement.loop = shouldLoop;

            // Update UI text and button states
            previewWidget.videoIndexText.textContent = `${previewWidget.currentVideoIndex + 1}/${previewWidget.videoUrls.length}`;
            previewWidget.prevButton.disabled = previewWidget.videoUrls.length <= 1;
            previewWidget.nextButton.disabled = previewWidget.videoUrls.length <= 1;

            previewWidget.mediaElement.style.display = 'block';
            previewWidget.controlsContainer.style.display = 'flex'; // Show controls
            recalculateComponentSize(targetComponent); // Recalculate size after changing content
        };

        // Attach update function to widget for external calls if needed (e.g., from onExecuted)
        previewWidget.updateVideoSource = updateVideoSource;
        previewWidget.navigateVideo = navigateVideo; // Expose navigate function
    }

    // Process new video data array
    previewWidget.videoUrls = [];
    if (videoDataArray && videoDataArray.length > 0) {
        videoDataArray.forEach(videoItem => {
            const [videoFilename, videoCategory] = videoItem;
            const params = {
                "filename": videoFilename,
                "subfolder": videoCategory,
                "type": "temp",
                "cachebuster": Math.random().toString().slice(2, 12)
            };
            const urlParameters = new URLSearchParams(params);
            previewWidget.videoUrls.push(`api/view?${urlParameters.toString()}`);
        });
    }

    // Reset index to 0 when new videos are loaded
    previewWidget.currentVideoIndex = 0;
    // Update the video player with the first video (or clear if none)
    previewWidget.updateVideoSource();

    // Adjust the component's size after setting up
    recalculateComponentSize(targetComponent);
}

/**
 * Adjusts the size of the given component based on its content.
 * @param {object} component The component whose size needs adjustment.
 */
function recalculateComponentSize(component) {
    const updatedSize = component.computeSize([component.size[0], component.size[1]]);
    component.setSize([component.size[0], updatedSize[1]]);
    component?.graph?.setDirtyCanvas(true); // Signal the canvas to redraw
}

// Register the custom extension with the application
app.registerExtension({
    name: "custom.VeoPreviewWithNav",
    async beforeRegisterNodeDef(nodeType, nodeData, appInstance) {
        if (nodeData?.name === "VeoVideoSaveAndPreview") {
            nodeType.prototype.onExecuted = function(data) {
                const videoData = data.video || []; // Expected format: [[filename1, category1], [filename2, category2], ...]

                const autoPlaySetting = this.widgets.find(w => w.name === "autoplay")?.value ?? false;
                const muteSetting = this.widgets.find(w => w.name === "mute")?.value ?? true;
                const loopSetting = this.widgets.find(w => w.name === "loop")?.value ?? false;

                // Pass the array of video data to the new function
                initializeSingleVideoPreviewWithNavigation(this, videoData, autoPlaySetting, muteSetting, loopSetting);
            };
        }
    }
});
