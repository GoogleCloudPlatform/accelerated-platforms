import gradio as gr
import re
import requests

# TEXT_EMBEDDING_ENDPOINT = "http://0.0.0.0:8000/embeddings/text
MULTIMODAL_EMBEDDING_ENDPOINT = "http://0.0.0.0:8000/embeddings/multimodal"


def is_valid_gcs_uri(uri):
    """
    Checks if the given URI is a valid Google Cloud Storage (GCS) URI.

    Args:
      uri: The URI to check.

    Returns:
      True if the URI is a valid GCS URI, False otherwise.
    """
    pattern = r"^gs://[a-z0-9][a-z0-9-]+[a-z0-9]/.*$"
    return re.match(pattern, uri) is not None


def validate_input(prompt, image_uri=None):
    """
    Validates the input prompt and optional image URI.

    Args:
      prompt: The text prompt.
      image_uri: The optional image URI.

    Returns:
      A tuple of (error_message, prompt, image_uri) where error_message is None if the inputs are valid,
      otherwise a string describing the error.
    """
    if not prompt:
        return "Prompt cannot be empty.", None, None
    if image_uri and not is_valid_gcs_uri(image_uri):
        return "Invalid GCS URI.", None, None
    return None, prompt, image_uri


def process_input(prompt, image_uri=None):
    """
    Processes the input prompt and optional image URI by calling the appropriate API.
    For retail scenarios, this could involve product search, information lookup,
    or visual question answering.

    Args:
      prompt: The text prompt (retail question).
      image_uri: The optional image URI (for visual questions).

    Returns:
      The API response.
    """
    if image_uri:
        # Call API that handles text + image input for retail
        response = call_retail_text_image_api(prompt, image_uri)
    else:
        # Call API that handles text-only retail questions
        response = call_retail_text_api(prompt)
    return response


def call_retail_text_api(prompt):
    """
    Calls the API for text-only retail questions.

    Args:
      prompt: The text prompt (retail question).

    Returns:
      The API response.
    """

    print(f"Calling retail text API with prompt: {prompt}")
    return "Response from retail text-only API"


def call_retail_text_image_api(prompt, image_uri):
    """
    Calls the API for text + image input for retail scenarios.

    Args:
      prompt: The text prompt (retail question).
      image_uri: The image URI.

    Returns:
      The API response.
    """
    # Replace this with your actual API call for retail text + image input
    print(
        f"Calling retail text+image API with prompt: {prompt} and image_uri: {image_uri}"
    )

    response = requests.post(
        MULTIMODAL_EMBEDDING_ENDPOINT,
        json={"caption": prompt, "image_uri": image_uri},
        headers={"Content-Type": "application/json"},
        timeout=1000,
    )
    print(response)
    return response


def chatbot_response(message, history):
    """
    Generates a response for the retail chatbot.

    Args:
      message: The user's message.
      history: The conversation history.

    Returns:
      The chatbot's response and updated history.
    """
    last_message = history[-1] if history else None
    if last_message and last_message["role"] == "user":
        prompt = last_message["content"]
        image_uri = last_message.get("image_uri")

        # Correctly call process_input here
        embeddings = process_input(prompt, image_uri)
        text_response = "Received embedding"  # Or generate from embeddings
        print(type(embeddings))
    else:
        embeddings = []
        text_response = "Please start the conversation with a prompt."

    history.append(
        {
            "role": "assistant",
            "content": text_response,
            "embeddings": embeddings,
        }
    )
    return "", history


with gr.Blocks(
    title="Retail Chatbot",
    theme=gr.themes.Monochrome(),
) as demo:
    gr.Markdown("# Retail Chatbot")
    gr.Markdown(
        "Ask questions about our products, get information, and even use images to find what you need!"
    )

    with gr.Row():
        with gr.Column():
            prompt = gr.Textbox(
                lines=2,
                placeholder="Enter your prompt here...",
                label="Ask your question",
            )
            image_uri = gr.Textbox(
                lines=1,
                placeholder="Optional: Enter a valid GCS image URI...",
                label="Enter your Image URI here",
            )
            submit_btn = gr.Button("Submit")

        with gr.Column():
            chatbot = gr.Chatbot(type="messages")

    submit_btn.click(
        fn=validate_input,
        inputs=[prompt, image_uri],
        outputs=[gr.Textbox(visible=False), prompt, image_uri],
    ).then(
        fn=lambda prompt, image_uri: ({"content": prompt, "image_uri": image_uri}, []),
        inputs=[prompt, image_uri],
        outputs=[chatbot, chatbot],
    ).then(
        fn=chatbot_response,
        inputs=[chatbot.value, chatbot.value],  # Access the history with chatbot.value
        outputs=[prompt, chatbot],
    )

demo.launch()
