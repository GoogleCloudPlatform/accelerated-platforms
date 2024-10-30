import requests


def query_emb_model(user_query):

    # Replace with your actual  service name and namespace
    # model_endpoint = "text-emb-job-l4.ml-team.svc.cluster.local"

    # Or simply the service name if in the same namespace
    model_endpoint = "text-emb-job-l4"

    url = f"http://{model_endpoint}:8000/get-text-embeddings"

    headers = {"Content-Type": "application/json"}

    data = {"product_desc": user_query}

    response = requests.post(url, headers=headers, json=data)
    print(response)
    print(response.json())
    response.raise_for_status()  # Raise an exception for error responses

    return response.json()["embeddings"]


# Example usage
if __name__ == "__main__":
    query = "I am looking for women's cycling short "  # TODO: Need to be dynamic
    generated_emb = query_emb_model(query)
    print(generated_emb)
