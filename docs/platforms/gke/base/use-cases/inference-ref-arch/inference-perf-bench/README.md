
⚙️ GKE Inference Benchmarking with inference-perf (OSS)
This README outlines the steps for setting up a performance evaluation environment on Google Kubernetes Engine (GKE), leveraging the GKE Inference Quickstart for model deployment and the inference-perf open-source tool for scalable benchmarking.

🎯 Goal
Measure the performance metrics like latency (Time-to-First-Token, Time-per-Output-Token) and throughput (Tokens/Requests per Second) of a Large Language Model (LLM) serving on GKE under simulated production load.

🚀Option 1: GCP Native benchmarks using GKE Inference Quickstart

The GKE Inference Quickstart (GIQ) provides validated, performance-tuned configurations, accelerating the deployment of your model server (e.g., vLLM, TGI).
📝 Prerequisites
Tools Installed:
Google Cloud CLI (gcloud): Authenticated to your project.
kubectl: Configured to access your cluster.
1. Choose Your Optimal Stack

Use the Google Cloud Console or the gcloud CLI to analyze cost and performance profiles:

CLI Method:
Bash

# List available optimized model profiles
gcloud container ai profiles list --location=us-central1

# View detailed benchmarks for a specific profile (e.g., Llama 3 on H100)
gcloud container ai profiles benchmarks list \
    --model-name=<MODEL_NAME> \
    --accelerator-type=<ACCELERATOR_TYPE> \
    --location=us-central1

2. Deploy the Model Server
Apply the generated manifest or deployment recipe from the Quickstart. The model server will be deployed as a Kubernetes Deployment or StatefulSet, often exposed via a GKE Inference Gateway or a standard Kubernetes Service.
Crucial step: Note the External IP or Cluster IP and Port of the deployed Kubernetes Service/Gateway. This will be the target URL for the benchmarking tool.


🚀Option 2: DIY -  Deploy and Run the inference-perf Benchmark

Inference-perf is the underlying platform for GIQ. To independantly run your own benchmarks and simulate production traffic and ensure the load generation is external to the model server pods, it is recommended to deploy the inference-perf tool as a Kubernetes Job on your GKE cluster, preferably using the provided Helm chart (if available) or a Job manifest.

📝 Prerequisites
Inference reference architecture is deployed for TPUs or GPUs on a GCP project with a running vLLM kubernetes service 
Pod monitoring / Automatic app monitoring with Google managed Prometheus 
Tools Installed:
Google Cloud CLI (gcloud): Authenticated to your project.
kubectl: Configured to access your cluster.
helm CLI: For deploying the inference-perf helm charts (OPTIONAL)

Run the Inference-perf TF 

Creates the GCS bucket for storing inference-perf results
Create the Kubernetes namespace and service account for the inference-perf workload 
Grants workload identity permissions for KSA for GCS, logging, and monitoring 

Define the Benchmarking Configuration

The inference-perf tool is configured entirely via the kubernetes manifest to create a ConfigMap and job.yaml defining the model, dataset, and load pattern.
Configure the environment variables 
Export Accelerator 
Export Model_ID
Note: Your vllm service endpoint should look something like this 
Optional: Update the configmap-benchmark.yaml with your custom load scenario and data set here 

📊 Step 3: Analyze and Interpret Results
The output reports (JSON files) contain all the measured metrics for each load stage.

Key LLM Performance Metrics
Metric
Description
Optimization Focus
Time-to-First-Token (TTFT)
Latency from request start to the first output token.
Crucial for perceived responsiveness in chatbots.
Time-per-Output-Token (TPOT)
Average time to generate subsequent tokens.
Key measure of generation speed and sustained throughput.
Total Latency (P95/P99)
End-to-end time for the entire response.
Represents the experience of users with the slowest responses.
Throughput (Tokens/s)
Total tokens generated per second under load.
Measure of infrastructure efficiency and capacity.


Analysis Insights:
High TTFT: Check your model server's configuration (e.g., prefill settings, batching), network connectivity, or KV cache utilization (if using GKE Inference Gateway).
High TPOT / Low Throughput: You may be hitting hardware saturation. Consider a more powerful accelerator or scaling up the number of replicas (which should be handled by HPA).
Latency Spikes during Load Change: The Horizontal Pod Autoscaler (HPA) may be reacting too slowly. Use the scaling metrics provided by GKE Inference Quickstart and tune the HPA target value or cool-down period.

📚 Resources
Tool
Description
Official Reference
inference-perf
GenAI inference performance benchmarking tool for K8s.
kubernetes-sigs/inference-perf (GitHub)
GKE Inference Quickstart
Provides verified configurations and benchmarks for deploying models on GKE.
GKE AI/ML documentation




