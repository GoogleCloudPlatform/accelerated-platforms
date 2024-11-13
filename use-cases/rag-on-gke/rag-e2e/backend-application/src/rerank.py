import requests
import logging

logging.basicConfig(level=logging.INFO)

gemma_it_endpoint = "rag-it-model-deployment-l4"


def query_pretrained_gemma(prompt):
    """
    Sends a request to the VLLM endpoint for text completion.

    Args:
      prompt: The text prompt for the model.

    Returns:
      The generated text response from the VLLM model.
    """

    url = f"http://{gemma_it_endpoint}.ml-team:8000/v1/chat/completions"

    headers = {"Content-Type": "application/json"}

    data = {
        "model": "google/gemma-2-2b-it",
        "messages": [{"role": "user", "content": f"{prompt}"}],
        "temperature": 0.7,  # Lowered temperature to make it more deterministic and focused
        "max_tokens": 384,  # Increased max_tokens
        "top_p": 1.0,
        "top_k": 1.0,
    }

    response = requests.post(url, headers=headers, json=data)
    # print(response)
    # print(response.json())
    response.raise_for_status()  # Raise an exception for error responses

    # return response.json()["choices"][0]["text"]
    return response.json()["choices"][0]["message"]["content"]
