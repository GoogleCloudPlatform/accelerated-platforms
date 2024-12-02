from typing import Union, Optional
import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
import semantic_search  # Assuming this module is implemented
import alloydb_connect
import logging
import logging.config
from google.cloud.alloydb.connector import Connector
import prompt_helper
import rerank


# Logging configuration (adjust as needed)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Database and table configuration (replace with your actual values)
catalog_db = "product_catalog"
catalog_table = "clothes"
embedding_column = {
    "text": "text_embeddings",
    "image": "image_embeddings",
    "multimodal": "multimodal_embeddings",
}
row_count = 5  # No of matching products

app = FastAPI()


# Pydantic models for request body
class TextPrompt(BaseModel):
    text: str


class ImageUriPrompt(BaseModel):
    image_uri: str


class Prompt(BaseModel):
    text: Optional[str] = None  # Directly use str for text
    image: Optional[str] = None  # Directly use str for image_uri


# Dependency to get AlloyDB engine
def get_alloydb_engine():
    with Connector() as connector:
        engine = alloydb_connect.create_alloydb_engine(connector, catalog_db)
        yield engine


@app.post("/generate_product_recommendations/")
async def generate_product_recommendations(
    prompt: Prompt, engine=Depends(get_alloydb_engine)
):
    """
    Generates product recommendations based on a text, image, or image+text prompt.
    """
    try:
        if prompt.text and prompt.image:
            logging.info(f"Received text: {prompt.text} and image: {prompt.image}")
            product_list = semantic_search.find_matching_products(
                engine=engine,
                catalog_table=catalog_table,
                embedding_column=embedding_column["multimodal"],
                row_count=row_count,
                user_query=prompt.text,
                image_uri=prompt.image,
            )

        elif prompt.text:
            logging.info(f"Received text: {prompt.text}")
            product_list = semantic_search.find_matching_products(
                engine=engine,
                catalog_table=catalog_table,
                embedding_column=embedding_column["text"],
                row_count=row_count,
                user_query=prompt.text,
            )
            logging.info(f"product list returned by db: {product_list}")
            if not product_list:
                return JSONResponse(
                    content={"error": "No matching products found"}, status_code=404
                )
            prompt_list = prompt_helper.prompt_generation(
                user_query=prompt.text, search_result=product_list
            )
            logging.info(f"Prompt used to re-rank: {prompt_list}")
            reranked_result = rerank.query_pretrained_gemma(prompt_list)
            logging.info(f"Response to front end: {reranked_result}")
            print(reranked_result)
            return JSONResponse(content=reranked_result, status_code=200)
            # return reranked_result

        elif prompt.image:
            logging.info(f"Received image: {prompt.image}")
            product_list = semantic_search.find_matching_products(
                engine=engine,
                catalog_table=catalog_table,
                embedding_column=embedding_column["image"],
                row_count=row_count,
                image_uri=prompt.image,
            )

        else:
            raise ValueError("Please provide at least a text or an image prompt.")

        logging.info(f"Product list returned by DB: {product_list}")

        if not product_list:
            return JSONResponse(
                content={"error": "No matching products found"},
                status_code=404,
            )

        # Format the recommendations (replace with your actual formatting)
        formatted_recommendations = ", ".join(
            [str(product) for product in product_list]
        )  # Example formatting
        response = f"These are product recommendations for the given prompt: {formatted_recommendations}"

        return {"response": response}

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
