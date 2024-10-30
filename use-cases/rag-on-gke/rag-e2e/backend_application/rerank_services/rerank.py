import requests


def query_pretrained_gemma(prompt):
    """
    Sends a request to the VLLM endpoint for text completion.

    Args:
      prompt: The text prompt for the model.

    Returns:
      The generated text response from the VLLM model.
    """

    # Replace with your actual VLLM service name and namespace
    # vllm_endpoint = "vllm-openai-l4.ml-team.svc.cluster.local"

    # Or simply the service name if in the same namespace
    vllm_endpoint = "vllm-openai-l4"

    url = f"http://{vllm_endpoint}:8000/v1/completions"

    headers = {"Content-Type": "application/json"}

    data = {
        "model": "google/gemma-2-2b",
        "prompt": prompt,
        "temperature": 0.5,
        "max_tokens": 256,
    }

    response = requests.post(url, headers=headers, json=data)
    print(response)
    print(response.json())
    response.raise_for_status()  # Raise an exception for error responses

    return response.json()["choices"][0]["text"]


# Example usage
if __name__ == "__main__":
    prompt = "Once upon a time, in a land far away, "
    
    generated_text = query_pretrained_gemma(prompt)
    print(generated_text)
