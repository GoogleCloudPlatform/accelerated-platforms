# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

kubernetes_namespace_create   = true
kubernetes_version            = "1.28.0"
llm-d_infra_repo              = "https://llm-d-incubation.github.io/llm-d-infra/"
llm-d_infra_chart             = "llm-d-infra"
llm-d_infra_chart_version     = "v1.3.4"
llm-d_kubernetes_namespace    = "llm-d"
llm-d_release_name            = "inference-scheduling"
validate_manifests            = false
skip_tests                    = false
gaie_chart                    = "oci://registry.k8s.io/gateway-api-inference-extension/charts/inferencepool"
gaie_chart_version            = "v1.2.0-rc.1"
llm-d_httproute_name_internal = "llm-d-inference-scheduling"
llm-d_httproute_name_external = "llm-d-inference-scheduling-external"
llm-d_gateway_name_internal   = "infra-inference-scheduling-inference-gateway"
llm-d_gateway_name_external   = "infra-inference-scheduling-inference-gateway-external"
llm-d_inferencepool_name      = "gaie-inference-scheduling"
llm-d_huggingface_spc         = "huggingface-read-token"
llm-d_modelserver_sa          = "ms-inference-scheduling-llm-d-modelservice-sa"
llm-d_ms_deployment_name      = "ms-inference-scheduling-llm-d-modelservice"
llm-d_ms_proxy_image          = "ghcr.io/llm-d/llm-d-routing-sidecar:v0.4.0-rc.1"
llm-d_ms_cuda_image           = "ghcr.io/llm-d/llm-d-cuda:v0.3.1"
llm-d_model_name              = "Qwen/Qwen3-0.6B"
