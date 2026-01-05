# Intelligent inference scheduling with llm-d

This guide walks through the llm-d reference architecture that is deployed
through [Intelligent inference scheduling with llm-d guide](./README.md).

## Prerequisite

This architecture and workflow assumes that the reader is familiar with the
following GKE, Google Cloud Networking and llm-d components:

- [Gateway API resources](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/gateway-api#gateway_resources)
- [GKE Gateway Controller](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/gateway-api#gateway_controller)
- [Google Cloud Load Balancer through GKE](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/service-load-balancer#load_balancer_types)
- [Gateway API Inference Extension(GAIE)](https://github.com/kubernetes-sigs/gateway-api-inference-extension/tree/main/docs/proposals/0683-epp-architecture-proposal)
- [vLLM-Optimized Inference Schedule](https://llm-d.ai/docs/architecture)

## Architecture

![image](images/llm-d.png)

## Workflow

- User securely hits the Cloud Endpoint DNS from a web browser.
- The DNS resolves to an External IP mapped to a
  `Global External Load Balancer`.
- The `Global External Load Balancer` has a `HTTPRoute` that points to the
  Gradio chat GKE service as the backend. It also has a backend policy
  specifying that the request to the backend will have
  `IAP(Identity-aware proxy)` authentication enabled.
- The `Global External Load Balancer` routes the request via `IAP` to the Gradio
  chat GKE service backend.
- Gradio chat GKE service forwards the request to the Gradio GKE Deployment and
  the user will see the chat interface loading on the browser.
- When the user sends a request via chat interface, the request reaches the
  Gradio GKE deployment as explained in previous steps.
- The Gradio GKE deployment takes the chat message and routes the request to the
  `Internal Regional Load Balancer` fronting the llm-d deployment.
- The `Internal Regional Load Balancer` has a `HTTPRoute` attached to it that
  points to an `InferencePool` as the backend. This `InferencePool` contains the
  pods running the model server, specifically running the inference of
  Qwen3-0.6B via `vllm`.
- The `InferencePool` has a reference to the GAIE endpoint picker(`EPP`) which
  means that the `GKE Gateway Controller` instead of routing the request to the
  backend in round-robin fashion, will consult the `EPP` to provide it with the
  backend where the traffic should be routed.
- The `EPP` has
  [scheduling profiles](https://github.com/llm-d/llm-d-inference-scheduler/blob/main/docs/architecture.md)
  that defines how to score the pods in the `InferencePool`. The scoring is done
  on the metrics coming out of the pods.
- Once the `EPP` identifies the pod which should be used based on the scores, it
  returns its IP address to the `GKE Gateway Controller` corresponding to the
  `Internal Regional Load Balancer` which then routes the request to the pod.
