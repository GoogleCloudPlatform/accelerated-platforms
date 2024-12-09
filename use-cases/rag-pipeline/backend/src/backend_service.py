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

from typing import Optional
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

# Configure logging
logging.config.fileConfig("logging.conf")  # Make sure you have logging.conf configured
logger = logging.getLogger("backend")

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
    )
    logging.getLogger().setLevel(new_log_level)
    logger.setLevel(new_log_level)

# Database and table configuration (replace with your actual values)
catalog_db = os.environ.get("CATALOG_DB")
catalog_table = os.environ.get("CATALOG_TABLE_NAME")
embedding_column = {
    "text": os.environ.get("EMBEDDING_COLUMN_TEXT"),
    "image": os.environ.get("EMBEDDING_COLUMN_IMAGE"),
    "multimodal": os.environ.get("EMBEDDING_COLUMN_MULTIMODAL"),
}
row_count = os.environ.get("ROW_COUNT")  # No of matching products in production

app = FastAPI()


# Pydantic models for request body
class Prompt(BaseModel):
    text: Optional[str] = None  # Directly use str for text
    image_uri: Optional[str] = None  # Directly use str for image_uri


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
        reranked_result = None  # Initialize reranked_result

        if prompt.text and prompt.image_uri:
            logging.info(f"Received text: {prompt.text} and image: {prompt.image_uri}")
            product_list = semantic_search.find_matching_products(
                engine=engine,
                catalog_table=catalog_table,
                embedding_column=embedding_column["multimodal"],
                row_count=row_count,
                user_query=prompt.text,
                image_uri=prompt.image_uri,
            )
            logging.info(f"product list received by backend service: {product_list}")
            if not product_list:
                return JSONResponse(
                    content={"error": "No matching products found"}, status_code=404
                )
            prompt_list = prompt_helper.prompt_generation(
                search_result=product_list, user_query=prompt.text
            )
            logging.info(f"Prompt used to re-rank: {prompt_list}")
            reranked_result = rerank.query_instruction_tuned_gemma(prompt_list)
            logging.info(f"Response to front end: {reranked_result}")

        elif prompt.text:
            logging.info(f"Received text: {prompt.text}")
            product_list = semantic_search.find_matching_products(
                engine=engine,
                catalog_table=catalog_table,
                embedding_column=embedding_column["text"],
                row_count=row_count,
                user_query=prompt.text,
            )
            logging.info(f"product list received by backend service: {product_list}")
            if not product_list:
                return JSONResponse(
                    content={"error": "No matching products found"}, status_code=404
                )
            prompt_list = prompt_helper.prompt_generation(
                search_result=product_list, user_query=prompt.text
            )
            logging.info(f"Prompt used to re-rank: {prompt_list}")
            reranked_result = rerank.query_instruction_tuned_gemma(prompt_list)
            logging.info(f"Response to front end: {reranked_result}")

        elif prompt.image_uri:
            logging.info(f"Received image: {prompt.image_uri}")
            product_list = semantic_search.find_matching_products(
                engine=engine,
                catalog_table=catalog_table,
                embedding_column=embedding_column["image"],
                row_count=row_count,
                image_uri=prompt.image_uri,
            )
            logging.info(f"product list received by backend service: {product_list}")
            if not product_list:
                return JSONResponse(
                    content={"error": "No matching products found"}, status_code=404
                )

            # Image only search results will have no user_query
            prompt_list = prompt_helper.prompt_generation(
                search_result=product_list, user_query=None
            )
            logging.info(f"Prompt used to re-rank: {prompt_list}")
            reranked_result = rerank.query_instruction_tuned_gemma(prompt_list)
            logging.info(f"Response to front end: {reranked_result}")

        else:
            raise ValueError("Please provide at least a text or an image prompt.")

        # Check if reranked_result is still None (no valid prompt was processed)
        if reranked_result is None:
            return JSONResponse(
                content={"error": "No valid products found after re-ranking"},
                status_code=404,
            )

        return JSONResponse(content=reranked_result, status_code=200)

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
