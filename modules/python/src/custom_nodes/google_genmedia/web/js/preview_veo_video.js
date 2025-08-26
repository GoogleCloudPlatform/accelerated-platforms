/**
* Copyright 2025 Google LLC
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
* http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*/

// This is a preview version of veo custom node

import { app } from "../../../scripts/app.js";

// Helper to get a unique storage key for each node instance
function getNodeStorageKey(nodeId) {
    return `comfyui.veopreview.node_${nodeId}_videoData`;
}

// Function to save video data to localStorage
function saveVideoDataToLocalStorage(nodeId, videoData) {
    try {
        localStorage.setItem(getNodeStorageKey(nodeId), JSON.stringify(videoData));
    } catch (e) {
        console.error(`[VeoPreview] Node ${nodeId}: Failed to save video data to localStorage:`, e);
    }
}

// Function to load video data from localStorage
function loadVideoDataFromLocalStorage(nodeId) {
    try {
        const data = localStorage.getItem(getNodeStorageKey(nodeId));
        if (data) {
            return JSON.parse(data);
        }
    } catch (e) {
        console.error(`[VeoPreview] Node ${nodeId}: Failed to load video data from localStorage:`, e);
    }
    return null;
}


/**
 * Manages a single video preview widget for a given component, with navigation for multiple videos.
 * @param {object} targetComponent The component to which the video preview will be added.
 * @param {Array<object>} videoDataArray An array of objects, where each inner object is {filename, subfolder, duration, width, height, format}.
 * @param {boolean} currentAutoplay Whether the video should autoplay initially.
 * @param {boolean} currentMute Whether the video should be muted.
 * @param {boolean} currentLoop Whether the video should loop (applies to the currently playing video).
 */
function initializeSingleVideoPreviewWithNavigation(targetComponent, videoDataArray, currentAutoplay, currentMute, currentLoop) {
    // Ensure videoDataArray is an array before proceeding
    const videos = Array.isArray(videoDataArray) ? videoDataArray : (videoDataArray ? [videoDataArray] : []);

    let previewWidget = targetComponent._mediaPreviewWidget;

    // Create the video preview widget if it doesn't already exist
    if (!previewWidget) {
        const widgetContainer = document.createElement("div");
        const hostNode = targetComponent;

        previewWidget = targetComponent.addDOMWidget("media_preview", "videoOutput", widgetContainer, {
            serialize: false,
            hideOnZoom: false,
            getValue() { return widgetContainer.value; },
            setValue(val) { widgetContainer.value = val; },
        });

        previewWidget.videoUrls = [];
        previewWidget.currentVideoIndex = 0;

        previewWidget.computeSize = function(width) {
            if (this.mediaAspectRatio && !this.domElementWrapper.hidden) {
                let calculatedHeight = (hostNode.size[0] - 20) / this.mediaAspectRatio + 10;
                calculatedHeight += 40;
                return [width, calculatedHeight > 0 ? calculatedHeight : 0];
            }
            return [width, -4];
        };

        previewWidget.value = { hidden: false, paused: false, parameters: {} };
        previewWidget.domElementWrapper = document.createElement("div");
        previewWidget.domElementWrapper.className = "comfy_single_video_preview";
        previewWidget.domElementWrapper.style.width = "100%";
        widgetContainer.appendChild(previewWidget.domElementWrapper);

        previewWidget.mediaElement = document.createElement("video");
        previewWidget.mediaElement.controls = true;
        previewWidget.mediaElement.style.width = "100%";
        previewWidget.mediaElement.style.display = "block";

        previewWidget.controlsContainer = document.createElement("div");
        previewWidget.controlsContainer.style.display = "flex";
        previewWidget.controlsContainer.style.justifyContent = "space-between";
        previewWidget.controlsContainer.style.alignItems = "center";
        previewWidget.controlsContainer.style.marginTop = "10px";

        previewWidget.prevButton = document.createElement("button");
        previewWidget.prevButton.textContent = "Previous";
        previewWidget.prevButton.onclick = () => navigateVideo(-1);
        previewWidget.controlsContainer.appendChild(previewWidget.prevButton);

        previewWidget.videoIndexText = document.createElement("span");
        previewWidget.videoIndexText.textContent = "0/0";
        previewWidget.controlsContainer.appendChild(previewWidget.videoIndexText);

        previewWidget.nextButton = document.createElement("button");
        previewWidget.nextButton.textContent = "Next";
        previewWidget.nextButton.onclick = () => navigateVideo(1);
        previewWidget.controlsContainer.appendChild(previewWidget.nextButton);

        previewWidget.mediaElement.addEventListener("loadedmetadata", () => {
            previewWidget.mediaAspectRatio = previewWidget.mediaElement.videoWidth / previewWidget.mediaElement.videoHeight;
            recalculateComponentSize(targetComponent);
        });

        previewWidget.mediaElement.addEventListener("error", () => {
            console.error(`Error loading video: ${previewWidget.mediaElement.src}`);
            previewWidget.mediaElement.style.display = 'none';
            previewWidget.controlsContainer.style.display = 'none';
            recalculateComponentSize(targetComponent);
        });

        previewWidget.domElementWrapper.appendChild(previewWidget.mediaElement);
        previewWidget.domElementWrapper.appendChild(previewWidget.controlsContainer);
        previewWidget.domElementWrapper.hidden = previewWidget.value.hidden;

        targetComponent._mediaPreviewWidget = previewWidget;

        const navigateVideo = (direction) => {
            previewWidget.currentVideoIndex += direction;
            if (previewWidget.currentVideoIndex < 0) {
                previewWidget.currentVideoIndex = previewWidget.videoUrls.length - 1;
            } else if (previewWidget.currentVideoIndex >= previewWidget.videoUrls.length) {
                previewWidget.currentVideoIndex = 0;
            }
            updateVideoSource();
        };

        const updateVideoSource = () => {
            if (previewWidget.videoUrls.length === 0) {
                previewWidget.mediaElement.src = '';
                previewWidget.mediaElement.style.display = 'none';
                previewWidget.controlsContainer.style.display = 'none';
                previewWidget.videoIndexText.textContent = "0/0";
                previewWidget.mediaElement.load();
                return;
            }

            const currentUrl = previewWidget.videoUrls[previewWidget.currentVideoIndex];
            previewWidget.mediaElement.src = currentUrl;
            previewWidget.mediaElement.muted = previewWidget.shouldMute;
            previewWidget.mediaElement.loop = previewWidget.shouldLoop;
            previewWidget.mediaElement.autoplay = previewWidget.shouldAutoplay && !previewWidget.value.paused && !previewWidget.value.hidden;

            previewWidget.mediaElement.load();

            previewWidget.videoIndexText.textContent = `${previewWidget.currentVideoIndex + 1}/${previewWidget.videoUrls.length}`;
            previewWidget.prevButton.disabled = previewWidget.videoUrls.length <= 1;
            previewWidget.nextButton.disabled = previewWidget.videoUrls.length <= 1;

            previewWidget.mediaElement.style.display = 'block';
            previewWidget.controlsContainer.style.display = 'flex';
            recalculateComponentSize(targetComponent);
        };

        previewWidget.updateVideoSource = updateVideoSource;
        previewWidget.navigateVideo = navigateVideo;
    }

    // Always update settings and video data whenever this function is called
    previewWidget.shouldAutoplay = currentAutoplay;
    previewWidget.shouldMute = currentMute;
    previewWidget.shouldLoop = currentLoop;

    // Conditionally update previewWidget.videoUrls based on whether new data is provided
    if (videos && videos.length > 0) {
        previewWidget.videoUrls = []; // Clear existing only if new data is coming
        videos.forEach(videoItem => {
            const videoFilename = videoItem.filename;
            const videoCategory = videoItem.subfolder;

            const params = {
                "filename": videoFilename,
                "subfolder": videoCategory,
                "type": videoItem.type,
                "cachebuster": Date.now()
            };
            const urlParameters = new URLSearchParams(params);
            previewWidget.videoUrls.push(`api/view?${urlParameters.toString()}`);
        });
    }

    // If we have video URLs from either current execution or persisted data, update the source
    if (previewWidget.videoUrls.length > 0) {
        previewWidget.currentVideoIndex = 0;
        previewWidget.updateVideoSource();
    } else {
        previewWidget.mediaElement.src = '';
        previewWidget.mediaElement.style.display = 'none';
        previewWidget.controlsContainer.style.display = 'none';
        previewWidget.videoIndexText.textContent = "0/0";
        previewWidget.mediaElement.load();
    }

    recalculateComponentSize(targetComponent);
}

function recalculateComponentSize(component) {
    const updatedSize = component.computeSize([component.size[0], component.size[1]]);
    component.setSize([component.size[0], updatedSize[1]]);
    component?.graph?.setDirtyCanvas(true);
}

app.registerExtension({
    name: "custom.VeoPreviewWithNav",
    async beforeRegisterNodeDef(nodeType, nodeData, appInstance) {
        if (nodeData?.name === "VeoVideoSaveAndPreview") {

            const originalOnExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function(data) {
                // Ensure data.video is an array, even if it's a single item
                const videoData = data.video || [];
                const videoDataArray = Array.isArray(videoData) ? videoData : [videoData];

                saveVideoDataToLocalStorage(this.id, videoDataArray);

                const autoPlaySetting = this.widgets.find(w => w.name === "autoplay")?.value ?? false;
                const muteSetting = this.widgets.find(w => w.name === "mute")?.value ?? true;
                const loopSetting = this.widgets.find(w => w.name === "loop")?.value ?? false;

                initializeSingleVideoPreviewWithNavigation(this, videoDataArray, autoPlaySetting, muteSetting, loopSetting);

                if (originalOnExecuted) {
                    originalOnExecuted.apply(this, arguments);
                }
            };

            const originalOnConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function (nodeConfig) {
                if (originalOnConfigure) {
                    originalOnConfigure.apply(this, arguments);
                }
                
                const autoPlaySetting = this.widgets.find(w => w.name === "autoplay")?.value ?? (nodeConfig?.widgets_values?.autoplay ?? false);
                const muteSetting = this.widgets.find(w => w.name === "mute")?.value ?? (nodeConfig?.widgets_values?.mute ?? true);
                const loopSetting = this.widgets.find(w => w.name === "loop")?.value ?? (nodeConfig?.widgets_values?.loop ?? false);

                const storedVideoData = loadVideoDataFromLocalStorage(this.id);
                const storedVideoDataArray = storedVideoData ? (Array.isArray(storedVideoData) ? storedVideoData : [storedVideoData]) : [];

                if (storedVideoDataArray.length > 0) {
                    initializeSingleVideoPreviewWithNavigation(this, storedVideoDataArray, autoPlaySetting, muteSetting, loopSetting);
                }
            };

            if (!nodeType.prototype._visibilityListenerAdded) {
                nodeType.prototype._visibilityListenerAdded = true;

                document.addEventListener("visibilitychange", () => {
                    if (document.visibilityState === "visible") {
                        for (const node of app.graph._nodes) {
                            if (node.type === nodeData.name) {
                                const previewWidget = node._mediaPreviewWidget;
                                if (previewWidget && previewWidget.mediaElement && !previewWidget.value.hidden) {
                                    const mediaElement = previewWidget.mediaElement;

                                    if (previewWidget.videoUrls.length > 0) {
                                        previewWidget.updateVideoSource();

                                        if (previewWidget.shouldAutoplay && !previewWidget.value.paused) {
                                            setTimeout(() => {
                                                mediaElement.play().catch(e => {
                                                    console.warn(`Autoplay prevented for node ${node.id} on tab focus. User interaction may be required.`, e);
                                                });
                                            }, 100);
                                        }
                                    } else {
                                        const storedVideoDataFallback = loadVideoDataFromLocalStorage(node.id);
                                        const storedVideoDataFallbackArray = storedVideoDataFallback ? (Array.isArray(storedVideoDataFallback) ? storedVideoDataFallback : [storedVideoDataFallback]) : [];
                                        if (storedVideoDataFallbackArray && storedVideoDataFallbackArray.length > 0) {
                                            initializeSingleVideoPreviewWithNavigation(node, storedVideoDataFallbackArray, previewWidget.shouldAutoplay, previewWidget.shouldMute, previewWidget.shouldLoop);
                                            if (previewWidget.shouldAutoplay && !previewWidget.value.paused) {
                                                setTimeout(() => {
                                                    mediaElement.play().catch(e => {
                                                        console.warn(`Autoplay prevented for node ${node.id} after fallback init (autoplay policy).`, e);
                                                    });
                                                }, 100);
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    } else {
                        for (const node of app.graph._nodes) {
                            if (node.type === nodeData.name) {
                                const previewWidget = node._mediaPreviewWidget;
                                if (previewWidget && previewWidget.mediaElement) {
                                    previewWidget.mediaElement.pause();
                                }
                            }
                        }
                    }
                });
            }
        }
    }
});
