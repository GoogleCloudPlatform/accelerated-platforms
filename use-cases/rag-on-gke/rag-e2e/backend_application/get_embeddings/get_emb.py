import requests

service_name = "embedding-model-service"  # From your embedding-job.yaml
namespace = "ml-team"  # From your embedding-job.yaml
url = f"http://{service_name}.{namespace}.svc.cluster.local:8000/embeddings"
headers = {"Content-Type": "application/json"}


def get_text_embeddings(user_query):

    data = {"product_desc": user_query}
    try:
        response = requests.post(url, headers=headers, json=data)
        # print(response)
        print(response.json())
        response.raise_for_status()  # Raise an exception for error responses
        return response.json()["text_embeds"]
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Deployment: {e}")
        return None


def get_image_embeddings(image_uri):

    data = {"image_uri": image_uri}
    try:
        response = requests.post(url, headers=headers, json=data)
        # print(response)
        print(response.json())
        response.raise_for_status()  # Raise an exception for error responses
        return response.json()["image_embeds"]
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Deployment: {e}")
        return None


def get_multimodal_embeddings(desc, image_uri):

    data = {"product_desc": desc, "image_uri": image_uri}
    try:
        response = requests.post(url, headers=headers, json=data)
        # print(response)
        print(response.json())
        response.raise_for_status()  # Raise an exception for error responses
        return response.json()["multimodal_embeds"]
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Deployment: {e}")
        return None


if __name__ == "__main__":
    # TODO: Need to be dynamic. This is only for testing
    product_desc = "orange plum print man round neck t shirt buy red r online india shop apparel huge collection brand clothe"
    image_uri = "gs://gkebatchexpce3c8dcb-dev-processing/flipkart_images/1bf1d03b20279c6416349c2aba57431a_0.jpg"

    generated_text_emb = get_text_embeddings(product_desc)
    print(len(generated_text_emb))  # 768 dimensions

    generated_image_emb = get_image_embeddings(image_uri)
    print(len(generated_image_emb))  # 768 dimensions

    generated_emb = get_multimodal_embeddings(product_desc, image_uri)
    print(len(generated_emb))  # 768 dimensions
