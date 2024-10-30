# Deploy NVIDIA NIMs on GKE

This repository deploy. Meta's [llama3-8b-instruct NIM](https://build.nvidia.com/meta/llama3-8b) NIM serves as a demonstration model in this instance.

## Before you begin

1. Ensure that you have access to NVIDIA NIMs. You need to have the NVIDIA AI Enterprise License (NVAIE) to access the NIMs. To get started, go to [build.nvidia.com](https://build.nvidia.com/explore/discover?signin=true) and provide your company email address.

## How to use this repository

1. Clone the repository and change directory to the guide directory

   ```bash
   git clone https://github.com/GoogleCloudPlatform/ai-on-gke && \
   cd ai-on-gke/best-practices/ml-platform/terraform/features/nim
   ```

## Setup variables

1. Ensure that your `MLP_ENVIRONMENT_FILE` is configured

   ```bash
   cat ${MLP_ENVIRONMENT_FILE} && \
   source ${MLP_ENVIRONMENT_FILE}
   ```

   > You should see the various variables populated with the information specific to your environment.

1. Initialize the following Terraform variables

   ```hcl
   google_project   = # Google Cloud project ID
   cluster_name     = # The name of the cluster NIM will be deployed to
   cluster_location = # The location of the cluster NIM will be deployed to
   gpu_limits       = # Number of GPUs that will be presented to the model
   ngc_api_key      = # Your NGC API key
   ```

## Deploy the NIM with the Helm chart

1. Initialize Terraform

   ```bash
   terraform init
   ```

1. Review the proposed changes, and apply them

   ```bash
   terraform apply
   ```

   The whole provisioning process can take up to 10 minutes.

## Test the NIM

1. Get the model endpoint

   ```bash
   NIM_EXPOSED_IP=$(kubectl -n nim get svc/nim-nim-llm -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
   ```

1. Verify that the model is available

   ```bash
   curl -X GET "http://${NIM_EXPOSED_IP}:8000/v1/models"
   ```

   It should output the name of the deployed model

   ```json
   {
   "object": "list",
   "data": [
      {
         "id": "meta/llama3-8b-instruct",
         "object": "model",
         "created": 1727343384,
         "owned_by": "system",
         "root": "meta/llama3-8b-instruct",
         "parent": null,
         "permission": [
         {
            "id": "modelperm-cbfaf2c5d1b74b04b7bc551d30b25825",
            "object": "model_permission",
            "created": 1727343384,
            "allow_create_engine": false,
            "allow_sampling": true,
            "allow_logprobs": true,
            "allow_search_indices": false,
            "allow_view": true,
            "allow_fine_tuning": false,
            "organization": "*",
            "group": null,
            "is_blocking": false
         }
         ]
      }
   ]
   }
   ```

1. Test with a sample inference

   ```bash
   curl -X 'POST' \
      "http://${NIM_EXPOSED_IP}:8000/v1/chat/completions" \
      -H 'accept: application/json' \
      -H 'Content-Type: application/json' \
      -d '{
   "messages": [
      {
         "content": "You are a pirate chatbot who always responds in pirate speak!",
         "role": "system"
      },
      {
         "content": "Who are you?",
         "role": "user"
      }
   ],
   "model": "meta/llama3-8b-instruct",
   "max_tokens": 4096,
   "top_p": 1,
   "n": 1,
   "stream": false,
   "stop": "\n",
   "frequency_penalty": 0.0
   }'
   ```

   The model should return this output

   ```json
   {
      "id": "cmpl-d56ef22bf83049d880fea321e4c2d3b6",
      "object": "chat.completion",
      "created": 1727344215,
      "model": "meta/llama3-8b-instruct",
      "choices": [
      {
         "index": 0,
         "message":
         {
            "role": "assistant",
            "content": "Arrrr, shiver me timbers! Me be Captain Chatbot, the scurviest, most infamous pirate to ever sail the Seven Seas! Me be here to chat with ye, swabber, and share me tales of adventure, plunder, and grog-filled exploits! What be ye lookin' for, matey?"
         },
         "logprobs": null,
         "finish_reason": "stop",
         "stop_reason": 128009
      }],
      "usage":
      {
         "prompt_tokens": 32,
         "total_tokens": 102,
         "completion_tokens": 70
      }
   }
   ```

## Optional

By default the llama3-8b NIM is setup. If a different NIM is needed, follow these steps:

1. Initialize the following Terraform variables

   ```hcl
   image_name = # The name of the image to be deployed by NIM. Should be <org>/<model-name>
   image_tag  = # The tag of the image to be deployed by NIM
   ```

1. Review the proposed changes, and apply them

   ```bash
   terraform apply
   ```

   The new model will be deployed instead of llama3.