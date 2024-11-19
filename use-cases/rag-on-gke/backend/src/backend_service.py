# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import List, Union, Literal
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator, Field
import requests
import uvicorn
from llama_index.core.embeddings import BaseEmbedding

# Define the API Endpoints
TEXT_API_ENDPOINT = os.environ["TEXT_EMBEDDING_ENDPOINT"]
IMAGE_API_ENDPOINT = os.environ["IMAGE_EMBEDDING_ENDPOINT"]
MULTIMODAL_API_ENDPOINT = os.environ["MULTIMODAL_EMBEDDING_ENDPOINT"]

print("Text Embedding endpoint:", TEXT_API_ENDPOINT)
print("Image Embedding endpoint:", IMAGE_API_ENDPOINT)
print("Multimodal Embedding endpoint:", MULTIMODAL_API_ENDPOINT)


# FastAPI application
app = FastAPI()


# Request models
class TextRequest(BaseModel):
    """Request model for text embedding."""

    text: str


class ImageRequest(BaseModel):
    """Request model for image embedding."""

    image_uri: str


class MultimodalRequest(BaseModel):
    """Request model for image embedding."""

    image_uri: str
    text: str


class ImageEmbeddingResponse(BaseModel):
    """Response model for image embeddings."""

    image_embeds: List[float]


class TextEmbeddingResponse(BaseModel):
    """Response model for image embeddings."""

    text_embeds: List[float]


class MultimodalEmbeddingResponse(BaseModel):
    """Response model for image embeddings."""

    multimodal_embeds: List[float]


# Custom embedding class using BaseEmbedding
class CustomEmbedding(BaseEmbedding):
    """
    Custom embedding class that uses external APIs for text and image embeddings.
    """

    def __init__(self):
        """Initialize the CustomEmbedding class."""
        super().__init__()

    def _get_text_embedding(self, text: str) -> List[float]:  # Updated return type
        """
        Get text embedding from the external text embedding API.

        Args:
            text: The text to embed.

        Returns:
            An EmbeddingList object containing the text embedding.

        Raises:
            HTTPException: If the API request fails or returns an invalid response.
        """
        try:
            response = requests.post(
                TEXT_API_ENDPOINT,
                json={"caption": text},
                headers={"Content-Type": "application/json"},
                timeout=1000,
            )
            response.raise_for_status()

            text_embeddings = response.json()

            # Validate and extract the embedding list
            embedding_list = TextEmbeddingResponse.model_validate(
                text_embeddings
            ).text_embeds

            # Return the EmbeddingList directly
            return embedding_list
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=500, detail=f"Error fetching text embedding: {e}"
            )
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=500, detail=f"Invalid response from text embedding API: {e}"
            )

    def _get_image_embedding(
        self, image_uri: str
    ) -> List[float]:  # Updated return type
        """
        Get image embedding from the external image embedding API.

        Args:
            image_uri: The GCS URI of the image.

        Returns:
            An EmbeddingList object containing the image embedding.

        Raises:
            HTTPException: If the API request fails or returns an invalid response.
        """

        try:
            response = requests.post(
                IMAGE_API_ENDPOINT,
                json={"image_uri": image_uri},
                headers={"Content-Type": "application/json"},
                timeout=1000,
            )
            response.raise_for_status()

            image_embeddings = response.json()
            # print(type(image_embeddings))

            # Validate and extract the embedding list
            embedding_list = ImageEmbeddingResponse.model_validate(
                image_embeddings
            ).image_embeds

            # Return the EmbeddingList directly
            return embedding_list
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=500, detail=f"Error fetching image embedding: {e}"
            )
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid response from image embedding API: {e}",
            )

    def _get_multimodal_embedding(
        self, image_uri: str, text: str
    ) -> List[float]:  # Updated return type
        """
        Get image embedding from the external image embedding API.

        Args:
            image_uri: The GCS URI of the image.

        Returns:
            An EmbeddingList object containing the image embedding.

        Raises:
            HTTPException: If the API request fails or returns an invalid response.
        """

        try:
            response = requests.post(
                MULTIMODAL_API_ENDPOINT,
                json={"image_uri": image_uri, "caption": text},
                headers={"Content-Type": "application/json"},
                timeout=1000,
            )
            response.raise_for_status()

            multimodal_embeddings = response.json()

            # Validate and extract the embedding list
            embedding_list = MultimodalEmbeddingResponse.model_validate(
                multimodal_embeddings
            ).multimodal_embeds

            # Return the EmbeddingList directly
            return embedding_list
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=500, detail=f"Error fetching image embedding: {e}"
            )
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid response from image embedding API: {e}",
            )

    def get_text_embedding(self, text: str) -> List[float]:
        """
        Public method to get text embedding.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the text embedding.
        """
        return self._get_text_embedding(text)

    def get_image_embedding(self, image_uri: str) -> List[float]:
        """
        Public method to get image embedding.

        Args:
            image_uri: The GCS URI of the image.

        Returns:
            A list of floats representing the image embedding.
        """
        return self._get_image_embedding(image_uri)

    def get_multimodal_embedding(self, image_uri: str, text: str) -> List[float]:
        """
        Public method to get text embedding.

        Args:
            text: The text to embed.
            image_uri: The GCS URI of the image.

        Returns:
            A list of floats representing the text embedding.
        """
        return self._get_multimodal_embedding(image_uri, text)

    def _get_query_embedding(self, query: str) -> List:
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
            return TextEmbeddingResponse.model_validate(query_embeddings).embedding
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=500, detail=f"Error fetching query embedding: {e}"
            )
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid response from query embedding API: {e}",
            )

    async def _aget_query_embedding(self, query: str) -> List:
        """Asynchronous version of _get_query_embedding."""
        return self._get_query_embedding(query)


# Instantiate the embedding model
embedding_model = CustomEmbedding()


# Text embedding endpoint
@app.post("/embeddings/text", response_model=TextEmbeddingResponse)
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
        # Wrap the embedding list in EmbeddingList
        return TextEmbeddingResponse(text_embeds=embedding)

    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})


@app.post("/embeddings/image_uri", response_model=ImageEmbeddingResponse)
async def get_image_embedding(request: ImageRequest):
    """
    Endpoint for getting image embeddings.

    Args:
        request: The ImageRequest object image_uri: The GCS URI of the image.

    Returns:
        EmbeddingResponse containing the image embedding.
    """
    try:
        embedding = embedding_model.get_image_embedding(request.image_uri)
        # Return the EmbeddingResponse with the correct structure
        return ImageEmbeddingResponse(image_embeds=embedding)

    except Exception as e:  # Catch a broader range of exceptions
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")


@app.post("/embeddings/multimodal", response_model=MultimodalEmbeddingResponse)
async def get_multimodal_embedding(request: MultimodalRequest):
    """
    Endpoint for getting multimodal embeddings.

    Args:
        request: The ImageRequest object image_uri: The GCS URI of the image.
        request: The TextRequest object containing the text.

    Returns:
        EmbeddingResponse containing the multimodal embedding.
    """
    try:
        embedding = embedding_model.get_multimodal_embedding(
            request.image_uri, request.text
        )
        # Return the EmbeddingResponse with the correct structure
        return MultimodalEmbeddingResponse(multimodal_embeds=embedding)

    except Exception as e:  # Catch a broader range of exceptions
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")


# --- Start the web server ---

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)