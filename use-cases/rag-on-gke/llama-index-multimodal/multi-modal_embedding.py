import requests

def get_multimodal_embeddings(text, image_path):
    API_URL = ""  # Replace with your actual API endpoint
    
    with open(image_path, "rb") as image_file:
        files = {
            "image": image_file,
            "text": (None, text)
        }

        response = requests.post(API_URL, files=files)

    if response.status_code == 200:
        embeddings = response.json()["multimodal_embeds"]
        return embeddings
    else:
        print("Error getting multimodal embeddings:", response.status_code, response.text)
        return None

# Example usage
text= "orange plum print man round neck t shirt buy red r online india shop apparel huge collection brand clothe"
image_path = "t-shirt.jpg" 
embeddings = get_multimodal_embeddings(text, image_path)
if embeddings:
    print(embeddings)