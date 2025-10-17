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

// This is a preview version of Lyria custom node UI

import { app } from "../../../scripts/app.js";

function getNodeStorageKey(nodeId) {
    return `comfyui.lyriapreview.node_${nodeId}_audioData`;
}

function saveAudioDataToLocalStorage(nodeId, audioData) {
    try {
        localStorage.setItem(getNodeStorageKey(nodeId), JSON.stringify(audioData));
    } catch (e) {
        console.error(`[LyriaPreview] Node ${nodeId}: Failed to save audio data to localStorage:`, e);
    }
}

function loadAudioDataFromLocalStorage(nodeId) {
    try {
        const data = localStorage.getItem(getNodeStorageKey(nodeId));
        if (data) {
            return JSON.parse(data);
        }
    } catch (e) {
        console.error(`[LyriaPreview] Node ${nodeId}: Failed to load audio data from localStorage:`, e);
    }
    return null;
}

function initializeSingleAudioPreviewWithNavigation(targetComponent, audioDataArray, currentAutoplay, currentMute, currentLoop) {
    const audios = Array.isArray(audioDataArray) ? audioDataArray : (audioDataArray ? [audioDataArray] : []);

    let previewWidget = targetComponent._mediaPreviewWidget;

    if (!previewWidget) {
        const widgetContainer = document.createElement("div");
        const hostNode = targetComponent;

        previewWidget = targetComponent.addDOMWidget("media_preview", "audioOutput", widgetContainer, {
            serialize: false,
            hideOnZoom: false,
            getValue() { return widgetContainer.value; },
            setValue(val) { widgetContainer.value = val; },
        });

        previewWidget.audioUrls = [];
        previewWidget.currentAudioIndex = 0;

        previewWidget.computeSize = function(width) {
            if (!this.domElementWrapper.hidden) {
                return [width, 80]; // Fixed height for audio player
            }
            return [width, -4];
        };

        previewWidget.value = { hidden: false, paused: false, parameters: {} };
        previewWidget.domElementWrapper = document.createElement("div");
        previewWidget.domElementWrapper.className = "comfy_single_audio_preview";
        previewWidget.domElementWrapper.style.width = "100%";
        widgetContainer.appendChild(previewWidget.domElementWrapper);

        previewWidget.mediaElement = document.createElement("audio");
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
        previewWidget.prevButton.onclick = () => navigateAudio(-1);
        previewWidget.controlsContainer.appendChild(previewWidget.prevButton);

        previewWidget.audioIndexText = document.createElement("span");
        previewWidget.audioIndexText.textContent = "0/0";
        previewWidget.controlsContainer.appendChild(previewWidget.audioIndexText);

        previewWidget.nextButton = document.createElement("button");
        previewWidget.nextButton.textContent = "Next";
        previewWidget.nextButton.onclick = () => navigateAudio(1);
        previewWidget.controlsContainer.appendChild(previewWidget.nextButton);

        previewWidget.mediaElement.addEventListener("error", () => {
            console.error(`Error loading audio: ${previewWidget.mediaElement.src}`);
            previewWidget.mediaElement.style.display = 'none';
            previewWidget.controlsContainer.style.display = 'none';
            recalculateComponentSize(targetComponent);
        });

        previewWidget.domElementWrapper.appendChild(previewWidget.mediaElement);
        previewWidget.domElementWrapper.appendChild(previewWidget.controlsContainer);
        previewWidget.domElementWrapper.hidden = previewWidget.value.hidden;

        targetComponent._mediaPreviewWidget = previewWidget;

        const navigateAudio = (direction) => {
            previewWidget.currentAudioIndex += direction;
            if (previewWidget.currentAudioIndex < 0) {
                previewWidget.currentAudioIndex = previewWidget.audioUrls.length - 1;
            } else if (previewWidget.currentAudioIndex >= previewWidget.audioUrls.length) {
                previewWidget.currentAudioIndex = 0;
            }
            updateAudioSource();
        };

        const updateAudioSource = () => {
            if (previewWidget.audioUrls.length === 0) {
                previewWidget.mediaElement.src = '';
                previewWidget.mediaElement.style.display = 'none';
                previewWidget.controlsContainer.style.display = 'none';
                previewWidget.audioIndexText.textContent = "0/0";
                previewWidget.mediaElement.load();
                return;
            }

            const currentUrl = previewWidget.audioUrls[previewWidget.currentAudioIndex];
            previewWidget.mediaElement.src = currentUrl;
            previewWidget.mediaElement.muted = previewWidget.shouldMute;
            previewWidget.mediaElement.loop = previewWidget.shouldLoop;
            previewWidget.mediaElement.autoplay = previewWidget.shouldAutoplay && !previewWidget.value.paused && !previewWidget.value.hidden;

            previewWidget.mediaElement.load();

            previewWidget.audioIndexText.textContent = `${previewWidget.currentAudioIndex + 1}/${previewWidget.audioUrls.length}`;
            previewWidget.prevButton.disabled = previewWidget.audioUrls.length <= 1;
            previewWidget.nextButton.disabled = previewWidget.audioUrls.length <= 1;

            previewWidget.mediaElement.style.display = 'block';
            previewWidget.controlsContainer.style.display = 'flex';
            recalculateComponentSize(targetComponent);
        };

        previewWidget.updateAudioSource = updateAudioSource;
        previewWidget.navigateAudio = navigateAudio;
    }

    previewWidget.shouldAutoplay = currentAutoplay;
    previewWidget.shouldMute = currentMute;
    previewWidget.shouldLoop = currentLoop;

    if (audios && audios.length > 0) {
        previewWidget.audioUrls = [];
        audios.forEach(audioItem => {
            const params = {
                "filename": audioItem.filename,
                "subfolder": audioItem.subfolder,
                "type": audioItem.type,
                "cachebuster": Date.now()
            };
            const urlParameters = new URLSearchParams(params);
            previewWidget.audioUrls.push(`api/view?${urlParameters.toString()}`);
        });
    }

    if (previewWidget.audioUrls.length > 0) {
        previewWidget.currentAudioIndex = 0;
        previewWidget.updateAudioSource();
    } else {
        previewWidget.mediaElement.src = '';
        previewWidget.mediaElement.style.display = 'none';
        previewWidget.controlsContainer.style.display = 'none';
        previewWidget.audioIndexText.textContent = "0/0";
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
    name: "custom.LyriaPreviewWithNav",
    async beforeRegisterNodeDef(nodeType, nodeData, appInstance) {
        if (nodeData?.name === "LyriaAudioSaveAndPreview") {

            const originalOnExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function(data) {
                const audioData = data.audio || [];
                const audioDataArray = Array.isArray(audioData) ? audioData : [audioData];

                saveAudioDataToLocalStorage(this.id, audioDataArray);

                const autoPlaySetting = this.widgets.find(w => w.name === "autoplay")?.value ?? false;
                const muteSetting = this.widgets.find(w => w.name === "mute")?.value ?? true;
                const loopSetting = this.widgets.find(w => w.name === "loop")?.value ?? false;

                initializeSingleAudioPreviewWithNavigation(this, audioDataArray, autoPlaySetting, muteSetting, loopSetting);
            };

            const originalOnConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function (nodeConfig) {
                if (originalOnConfigure) {
                    originalOnConfigure.apply(this, arguments);
                }

                const autoPlaySetting = this.widgets.find(w => w.name === "autoplay")?.value ?? (nodeConfig?.widgets_values?.autoplay ?? false);
                const muteSetting = this.widgets.find(w => w.name === "mute")?.value ?? (nodeConfig?.widgets_values?.mute ?? true);
                const loopSetting = this.widgets.find(w => w.name === "loop")?.value ?? (nodeConfig?.widgets_values?.loop ?? false);

                const storedAudioData = loadAudioDataFromLocalStorage(this.id);
                const storedAudioDataArray = storedAudioData ? (Array.isArray(storedAudioData) ? storedAudioData : [storedAudioData]) : [];

                if (storedAudioDataArray.length > 0) {
                    initializeSingleAudioPreviewWithNavigation(this, storedAudioDataArray, autoPlaySetting, muteSetting, loopSetting);
                }
            };
        }
    }
});

