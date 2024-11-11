import requests
import logging

logging.basicConfig(level=logging.INFO)


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
        "temperature": 0.7,  # Lowered temperature to make it more deterministic and focused
        "max_tokens": 512,  # Increased max_tokens
    }

    response = requests.post(url, headers=headers, json=data)
    # print(response)
    # print(response.json())
    response.raise_for_status()  # Raise an exception for error responses

    return response.json()["choices"][0]["text"]


# Test:
# TODO: make it dynamic
if __name__ == "__main__":

    user_query = "I am looking for cycling shorts for women"

    search_result = """ 
      Name: Sportking Women's Leggings
      Description: sportke woman legging buy light green r online india shop apparel huge collection brand clothe
      category: Women's Clothing
      Specifications: {"Number of Contents in Sales Package": "Pack of 1", "Fabric": "Cotton Lycra", "Type": "Leggings", "Season": "SS14", "Pattern": "Solid", "Ideal For": "Women's", "Occasion": "Casual"}
    
      
      Name: Sportking Women's Leggings
      Description: sportke woman legging buy yellow r online india shop apparel huge collection brand clothe
      category: Women's Clothing
      Specifications: {"Number of Contents in Sales Package": "Pack of 1", "Fabric": "Cotton Lycra", "Type": "Leggings", "Season": "SS14", "Pattern": "Solid", "Occasion": "Casual", "Ideal For": "Women's"}
      
      
      Name: Sportking Women's Leggings
      Description: sportke woman legging buy multicolor r online india shop apparel huge collection brand clothe
      category: Women's Clothing
      Specifications: {"Number of Contents in Sales Package": "Pack of 2", "Fabric": "Cotton Lycra", "Type": "Leggings", "Season": "SS14", "Pattern": "Solid", "Ideal For": "Women's", "Occasion": "Casual"}
      
      
      Name: Younky Women's Sports Bra
      Description: younky woman sport bra price rs red seemless air
      category: Women's Clothing
      Specifications: {"Brand Color": "Red", "color": "Red", "Pattern": "Solid", "Occasion": "Sports", "Ideal For": "Women's", "Wire Support": "Wirefree", "Straps": "Regular", "Number of Contents in Sales Package": "Pack of 1", "Fabric": "Spandax", "Type": "Sports Bra"}
      
      
      Name: Addline Women's Leggings
      Description: addline woman legging buy royal blue red r online india shop apparel huge collection brand clothe
      category: Women's Clothing
      Specifications: {"Ideal For": "Women's", "Pattern": "Solid", "Type": "Leggings", "Fabric": "Cotton, Cotton-Spandex", "Number of Contents in Sales Package": "Pack of 2"}
      """

    # Option 1: Emphasize User Intent
    prompt1 = f"""An online shopper is searching for products.  
    Given their query and a list of initial product recommendations, identify ONLY the TOP 3 products that best match the shopper's intent. 
    Search Query: {user_query}. 
    Product List: 
    {search_result}"""

    # Option 2:  Provide Context and Constraints
    prompt2 = f"""You are an AI assistant helping an online shopper find the most relevant products.  
    The shopper has submitted a search query, and a preliminary search has returned a list of potential matches. 
    Your task is to refine these results by selecting the 3 best product recommendations from the list. 
    Search Query: {user_query}. 
    Product List: 
    {search_result}"""

    # Option 3:  Be More Directive
    prompt3 = f"""Rerank the following product recommendations to best satisfy an online shopper's search query. 
    Return only the top 3 most relevant products. 
    Search Query: {user_query}. 
    Product List: 
    {search_result}"""

    generated_text1 = query_pretrained_gemma(prompt1)
    logging.info(generated_text1)

    generated_text2 = query_pretrained_gemma(prompt2)
    logging.info(generated_text2)

    generated_text3 = query_pretrained_gemma(prompt3)
    logging.info(generated_text3)
