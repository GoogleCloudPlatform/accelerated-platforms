import gradio as gr
import requests

# URLs of your custom LLMs (replace with actual URLs)
MODEL_URLS = {
    "modelA": "http://104.198.185.85:8000/v1/chat/completions",
    # "modelB": "YOUR_MODEL_B_API_URL",
    # Add more models as needed
}


def chatbot(message, history):
    history = history or []
    history.append([message, None])

    # Get the selected model's URL
    # model_url = MODEL_URLS.get(model)
    # if not model_url:
    #     raise ValueError(f"Invalid model selected: {model}")

    # Construct the prompt for the selected model
    # (Adjust based on your API's requirements)
    prompt = ""
    for user_msg, bot_msg in history:
        prompt += f"Customer: {user_msg}\nRetail Bot: {bot_msg}\n"
    prompt += f"Customer: {message}\nRetail Bot: "

    # model_url = "http://34.171.174.67:8000/v1/chat/completions"
    model_url = MODEL_URLS.get("modelA")
    model_name = "/data/models/model-gemma2-a100/experiment-a2aa2c3it1"

    # Send request to the selected model API
    response = requests.post(
        model_url,
        headers={"content-type": "application/json"},
        timeout=100,
        json={
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.70,
            "top_p": 1.0,
            "top_k": 1.0,
            "max_tokens": 256,
        },
        stream=False,
    )

    # Extract the generated response
    # (Adjust based on your API's response format)
    try:
        bot_message = response.json()["choices"][0]["message"]["content"]
        print(bot_message)
    except KeyError:
        raise ValueError("Invalid response format from the model API")

    history[-1][1] = bot_message
    return history, history


# Create the Gradio interface
iface = gr.Interface(
    fn=chatbot,
    inputs=["text"],
    outputs=[
        gr.Chatbot(label="Retail Chatbot"),
        gr.Chatbot(label="Conversation History"),
    ],
    title="Retail Customer Chatbot",
    description="Ask your retail questions here!",
    theme=gr.themes.Soft(),
)

iface.launch(debug=True)
