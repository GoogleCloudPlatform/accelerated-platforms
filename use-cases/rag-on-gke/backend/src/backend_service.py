from typing import List

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel, RootModel
import requests
import uvicorn
from llama_index.core.embeddings import BaseEmbedding

# Define the API Endpoints
TEXT_API_ENDPOINT = "http://34.27.238.63:8080/embed"  # Replace with your actual text embedding API endpoint
IMAGE_API_ENDPOINT = ""  # Replace with your actual image embedding API endpoint

app = FastAPI()


# Custom embedding class using BaseEmbedding
class CustomEmbedding(BaseEmbedding):
    """
    Custom embedding class that uses external APIs for text and image embeddings.
    """

    def __init__(self):
        """Initialize the CustomEmbedding class."""
        super().__init__()

    def _get_text_embedding(self, text: str) -> float:
        """
        Get text embedding from the external text embedding API.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the text embedding.

        Raises:
            HTTPException: If the API request fails or returns an invalid response.
        """
        try:
            # text = "What is Deep Learning?"

            response = requests.post(
                TEXT_API_ENDPOINT,
                json={"inputs": text},  # Changed "text" to "inputs"
                headers={
                    "Content-Type": "application/json"
                },  # Added content-type header
                timeout=1000,
            )

            # response = requests.post(
            #     TEXT_API_ENDPOINT, json={"text": text}, timeout=1000
            # )
            response.raise_for_status()

            text_embeddings = response.json()
            return text_embeddings
            # return EmbeddingResponse.model_validate(text_embeddings).embedding
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=500, detail=f"Error fetching text embedding: {e}"
            )
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=500, detail=f"Invalid response from text embedding API: {e}"
            )

    def _get_image_embedding(self, image: bytes) -> List[float]:
        """
        Get image embedding from the external image embedding API.

        Args:
            image: The image bytes to embed.

        Returns:
            A list of floats representing the image embedding.

        Raises:
            HTTPException: If the API request fails or returns an invalid response.
        """
        try:
            response = requests.post(
                IMAGE_API_ENDPOINT,
                files={"image": image},
                timeout=1000,
            )
            response.raise_for_status()

            image_embeddings = response.json()
            return EmbeddingResponse.model_validate(image_embeddings).embedding
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=500, detail=f"Error fetching image embedding: {e}"
            )
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid response from image embedding API: {e}",
            )

    def get_text_embedding(self, text: str) -> float:
        """
        Public method to get text embedding.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the text embedding.
        """
        return self._get_text_embedding(text)

    def get_image_embedding(self, image_file: bytes) -> List[float]:
        """
        Public method to get image embedding.

        Args:
            image_file: The image bytes to embed.

        Returns:
            A list of floats representing the image embedding.
        """
        return self._get_image_embedding(image_file)

    def _get_query_embedding(self, query: str) -> List[float]:
        """
        Get query embedding from the external text embedding API.

        Args:
            query: The query string to embed.

        Returns:
            A list of floats representing the query embedding.

        Raises:
            HTTPException: If the API request fails or returns an invalid response.
        """
        try:
            response = requests.post(
                TEXT_API_ENDPOINT, json={"text": query}, timeout=1000
            )
            response.raise_for_status()

            query_embeddings = response.json()
            return EmbeddingResponse.model_validate(query_embeddings).embedding
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=500, detail=f"Error fetching query embedding: {e}"
            )
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid response from query embedding API: {e}",
            )

    async def _aget_query_embedding(self, query: str) -> List[float]:
        """Asynchronous version of _get_query_embedding."""
        return self._get_query_embedding(query)


# FastAPI application
app = FastAPI()

# Instantiate the embedding model
embedding_model = CustomEmbedding()


# Request models
class TextRequest(BaseModel):
    """Request model for text embedding."""

    text: str


class ImageRequest(BaseModel):
    """Request model for image embedding."""

    pass  # No specific data needed for image, as it's uploaded separately


# Response models
class EmbeddingResponse(RootModel[List[float]]):
    """Response model for embeddings."""

    # __root__: RootModel[List[float]]
    # # embedding: List[float]


# Text embedding endpoint
@app.post("/embeddings/text", response_model=EmbeddingResponse)
async def get_text_embedding(request: TextRequest):
    """
    Endpoint for getting text embeddings.

    Args:
        request: The TextRequest object containing the text.

    Returns:
        EmbeddingResponse containing the text embedding.
    """
    try:
        embedding = embedding_model.get_text_embedding(request.text)
        return embedding
        # return EmbeddingResponse(embedding=embedding)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})


@app.post("/embeddings/image", response_model=EmbeddingResponse)
async def get_image_embedding(request: ImageRequest, image: UploadFile = File(...)):
    """
    Endpoint for getting image embeddings.

    Args:
        request: The ImageRequest object.
        image: The uploaded image file.

    Returns:
        EmbeddingResponse containing the image embedding.
    """
    try:
        image_data = await image.read()
        embedding = embedding_model.get_image_embedding(image_data)
        return EmbeddingResponse(embedding=embedding)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})


# --- Start the web server ---

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
