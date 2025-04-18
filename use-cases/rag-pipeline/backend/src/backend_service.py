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
import os
import traceback

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import get_aggregated_resources, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_cloud_trace(app):
    """Configures OpenTelemetry tracing with Cloud Trace exporter."""

    try:
        # Create a BatchSpanProcessor and add the exporter to it
        span_processor = BatchSpanProcessor(OTLPSpanExporter())

        # Detect environment. Set project ID if running on GCP
        gcp_project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        resource = get_aggregated_resources(
            [
                Resource.create(
                    {
                        "service.name": "rag-service",
                        "service.version": "1.0",
                        "cloud.provider": "gcp",
                        "cloud.project.id": gcp_project_id,
                    }
                )
            ]
        )

        # Create a TracerProvider and add the span processor
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(span_processor)

        # Set the TracerProvider as the global provider
        trace.set_tracer_provider(provider)

        # Instrument FastAPI app for automatic tracing
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

        # Get the tracer
        tracer = trace.get_tracer(__name__)

        # Configure custom logging to include trace_id and span_id
        LoggingInstrumentor().instrument(set_logging_format=True)

        logging.info("Cloud Trace configured successfully.")
        return tracer  # Return the tracer

    except Exception as e:
        logging.error(f"Error configuring Cloud Trace: {e}")
        traceback.print_exc()
        return None  # Or handle the error appropriately


# Assuming this is your FastAPI application
app = FastAPI()
# Get a tracer instance
tracer = configure_cloud_trace(app)


@app.get("/")
async def root():
    if tracer:
        with tracer.start_as_current_span("root_span") as root_span:
            root_span.set_attribute(
                "custom_attribute", "some-value"
            )  # add some custom span attributes
            logging.info(
                "This log message will include trace and span IDs."
            )  # This will automatically be instrumented with the trace_id and span_id

    return {"message": "Cloud Trace Manual Span Example"}


# Configure logging
logging.config.fileConfig("logging.conf")  # Make sure you have logging.conf configured
logger = logging.getLogger(__name__)

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
    )
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
            logger.info(f"Received text: {prompt.text} and image: {prompt.image_uri}")
            product_list = semantic_search.find_matching_products(
                engine=engine,
                catalog_table=catalog_table,
                embedding_column=embedding_column["multimodal"],
                row_count=row_count,
                user_query=prompt.text,
                image_uri=prompt.image_uri,
            )
            logger.info(f"product list received by backend service: {product_list}")
            if not product_list:
                return JSONResponse(
                    content={"error": "No matching products found"}, status_code=404
                )
            prompt_list = prompt_helper.prompt_generation(
                search_result=product_list, user_query=prompt.text
            )
            logger.info(f"Prompt used to re-rank: {prompt_list}")
            reranked_result = rerank.query_instruction_tuned_gemma(prompt_list)
            logger.info(f"Response to front end: {reranked_result}")

        elif prompt.text:
            logger.info(f"Received text: {prompt.text}")
            product_list = semantic_search.find_matching_products(
                engine=engine,
                catalog_table=catalog_table,
                embedding_column=embedding_column["text"],
                row_count=row_count,
                user_query=prompt.text,
            )
            logger.info(f"product list received by backend service: {product_list}")
            if not product_list:
                return JSONResponse(
                    content={"error": "No matching products found"}, status_code=404
                )
            prompt_list = prompt_helper.prompt_generation(
                search_result=product_list, user_query=prompt.text
            )
            logger.info(f"Prompt used to re-rank: {prompt_list}")
            reranked_result = rerank.query_instruction_tuned_gemma(prompt_list)
            logger.info(f"Response to front end: {reranked_result}")

        elif prompt.image_uri:
            logger.info(f"Received image: {prompt.image_uri}")
            product_list = semantic_search.find_matching_products(
                engine=engine,
                catalog_table=catalog_table,
                embedding_column=embedding_column["image"],
                row_count=row_count,
                image_uri=prompt.image_uri,
            )
            logger.info(f"product list received by backend service: {product_list}")
            if not product_list:
                return JSONResponse(
                    content={"error": "No matching products found"}, status_code=404
                )

            # Image only search results will have no user_query
            prompt_list = prompt_helper.prompt_generation(
                search_result=product_list, user_query=None
            )
            logger.info(f"Prompt used to re-rank: {prompt_list}")
            reranked_result = rerank.query_instruction_tuned_gemma(prompt_list)
            logger.info(f"Response to front end: {reranked_result}")

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
        logger.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
