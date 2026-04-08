// Copyright 2026 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import http from "k6/http";
import { check, sleep } from "k6";
import exec from "k6/execution";

const TARGET_URL = __ENV.TARGET_URL || "http://localhost:8000/generate";
const ACCELERATOR_NAME = __ENV.ACCELERATOR_NAME || "unknown";
const INFERENCE_SERVER_TYPE = __ENV.INFERENCE_SERVER_TYPE || "unknown";

// Extract hostname for deployment_name tag
const urlMatch = TARGET_URL.match(/https?:\/\/([^\/:]+)/);
const DEPLOYMENT_NAME = urlMatch ? urlMatch[1] : "unknown";

// Parse dynamic scenarios
if (!__ENV.SCENARIOS_JSON) {
  throw new Error("SCENARIOS_JSON environment variable is required.");
}

let configScenarios = [];
try {
  configScenarios = JSON.parse(__ENV.SCENARIOS_JSON);
} catch (e) {
  throw new Error(`Failed to parse SCENARIOS_JSON: ${e.message}`);
}

const MODEL_ID = configScenarios[0].model_id || "unknown";
const SEED = 42;

// Validate first scenario for warmup
if (
  !configScenarios[0].width ||
  !configScenarios[0].height ||
  !configScenarios[0].steps
) {
  throw new Error(
    "Each scenario in SCENARIOS_JSON must specify 'width', 'height', and 'steps'.",
  );
}

console.log(
  `Loaded ${configScenarios.length} benchmark scenarios for model ${MODEL_ID}: ${JSON.stringify(configScenarios)}`,
);

// Lookup table for scenario configurations
const SCENARIO_CONFIGS = {
  warmup: {
    batch: configScenarios[0].batch,
    vus: configScenarios[0].vus,
    steps: configScenarios[0].steps,
    width: configScenarios[0].width,
    height: configScenarios[0].height,
    model_id: MODEL_ID,
  },
};

// Build k6 scenarios object
const scenarios = {
  warmup: {
    executor: "constant-vus",
    vus: configScenarios[0].vus,
    duration: "5m",
    exec: "generate",
    tags: {
      scenario: "warmup",
      batch_size: configScenarios[0].batch.toString(),
      vus: configScenarios[0].vus.toString(),
      num_inference_steps: configScenarios[0].steps.toString(),
      width: configScenarios[0].width.toString(),
      height: configScenarios[0].height.toString(),
      inference_server: INFERENCE_SERVER_TYPE,
    },
  },
};

let currentTimeOffsetSeconds = 300; // 5m warmup
const COOL_DOWN_SECONDS = 30;

configScenarios.forEach((s, index) => {
  if (!s.width || !s.height || !s.steps) {
    throw new Error(
      `Scenario ${index} is missing required fields: width, height, or steps.`,
    );
  }
  const accelTag = (__ENV.ACCELERATOR_NAME || "unknown")
    .toLowerCase()
    .replace(/_/g, "-");
  const scenarioName = `bench_${accelTag}_b${s.batch}_v${s.vus}_s${s.steps}_r${s.width}x${s.height}`;
  const startTime = currentTimeOffsetSeconds + index * COOL_DOWN_SECONDS;

  scenarios[scenarioName] = {
    executor: "constant-vus",
    vus: s.vus,
    duration: s.duration || "10m",
    startTime: `${startTime}s`,
    exec: "generate",
    tags: {
      scenario: scenarioName,
      batch_size: s.batch.toString(),
      vus: s.vus.toString(),
      num_inference_steps: s.steps.toString(),
      width: s.width.toString(),
      height: s.height.toString(),
      inference_server: INFERENCE_SERVER_TYPE,
    },
  };

  SCENARIO_CONFIGS[scenarioName] = {
    batch: s.batch,
    vus: s.vus,
    steps: s.steps,
    width: s.width,
    height: s.height,
    model_id: s.model_id || MODEL_ID,
  };

  let durationSeconds = 600; // 10m default
  if (typeof s.duration === "string") {
    if (s.duration.endsWith("m"))
      durationSeconds = parseInt(s.duration.slice(0, -1)) * 60;
    else if (s.duration.endsWith("s"))
      durationSeconds = parseInt(s.duration.slice(0, -1));
  }
  currentTimeOffsetSeconds += durationSeconds;
});

export const options = {
  tags: {
    model: MODEL_ID,
    accelerator: ACCELERATOR_NAME,
    seed: SEED.toString(),
    target_url: TARGET_URL,
    deployment_name: DEPLOYMENT_NAME,
  },
  discardResponseBodies: false, // Need body for validation and error reporting
  scenarios: scenarios,
  thresholds: {
    http_req_failed: ["rate<0.05"],
  },
};

const params = {
  headers: {
    "Content-Type": "application/json",
  },
  timeout: "120s",
};

export function setup() {
  console.log(`Starting dynamic k6 load test against: ${TARGET_URL}`);
  console.log(
    `Running ${Object.keys(scenarios).length} scenarios (including warmup)`,
  );
}

let lastScenario = "";
let consecutiveFailures = 0;
let abortCurrentScenario = false;

export function generate() {
  const scenarioName = exec.scenario.name;
  const config = SCENARIO_CONFIGS[scenarioName];

  if (!config) {
    throw new Error(`No configuration found for scenario: ${scenarioName}`);
  }

  if (scenarioName !== lastScenario) {
    console.log(
      `VU ${exec.vu.idInTest} starting scenario: ${scenarioName} (Batch: ${config.batch}, VUs: ${config.vus})`,
    );
    lastScenario = scenarioName;
    consecutiveFailures = 0;
    abortCurrentScenario = false;
  }

  if (abortCurrentScenario) {
    sleep(1);
    return;
  }

  let payload;
  let endpoint = TARGET_URL;

  if (INFERENCE_SERVER_TYPE === "sglang") {
    endpoint = `${TARGET_URL}/v1/images/generations`;
    payload = JSON.stringify({
      model: `/gcs/${config.model_id}`,
      prompt:
        "A highly detailed, cinematic photograph of a futuristic city skyline at sunset, neon lights, 8k resolution, photorealistic",
      n: config.batch,
      size: `${config.width}x${config.height}`,
      num_inference_steps: config.steps,
      seed: SEED,
      response_format: "b64_json",
    });
  } else {
    payload = JSON.stringify({
      prompt:
        "A highly detailed, cinematic photograph of a futuristic city skyline at sunset, neon lights, 8k resolution, photorealistic",
      width: config.width,
      height: config.height,
      num_inference_steps: config.steps,
      seed: SEED,
      batch_size: config.batch,
    });
  }

  if (consecutiveFailures === 0) {
      console.log(`Endpoint: ${endpoint}`);
      console.log(`Payload: ${payload}`);
  }

  const res = http.post(endpoint, payload, params);

  const success = check(res, {
    "is status 200": (r) => r.status === 200,
    "has body": (r) => r.body && r.body.length > 0,
  });

  if (!success) {
    consecutiveFailures++;
    if (consecutiveFailures === 1) {
      console.error(
        `Request failed! Status: ${res.status}. Body: ${res.body || "empty"}`,
      );
    }
    if (consecutiveFailures >= 3) {
      console.error(`Scenario ${scenarioName} aborted due to 3 consecutive failures.`);
      abortCurrentScenario = true;
    }
    sleep(1);
  } else {
    consecutiveFailures = 0;
  }

  sleep(0.01);
}
