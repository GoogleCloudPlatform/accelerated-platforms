# alloy-db-setup-job.py
import asyncio
import logging
import logging.config
import os
import create_catalog  # Import the module, not individual functions

# ... (environment variables - no changes needed)

if __name__ == "__main__":
    logging.config.fileConfig("logging.conf")  # Configure logging early
    logger = logging.getLogger(__name__)

    # ... (log level setup from environment – No changes needed)

    try:
        # ... (Database creation - No changes needed)


        # ETL 
        logger.info("ETL job to create table and generate embeddings in progress ...")
        asyncio.run(
            create_catalog.create_and_populate_table(  # Correct call with arguments
                catalog_db, catalog_table, processed_data_path, max_workers_value
            )
        )  # Close asyncio.run here for clarity
        logger.info("ETL job has been completed successfully ...")

        # ... (Index creation - No changes needed)

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")  # Use .exception for stack trace
        raise  # Re-raise for visibility

    finally:
        logger.info("Catalog onboarding job has been completed.")



# create_catalog.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import logging.config
import os
import pandas as pd
import sqlalchemy
# ... other imports


# ... (create_database function – no changes needed)


async def create_and_populate_table(database, table_name, processed_data_path, max_workers_value):
    """Creates and populates table, generating embeddings concurrently."""
    try:
        # ... (Data extraction)

        with ThreadPoolExecutor(max_workers=max_workers_value) as executor:
            loop = asyncio.get_event_loop()
            all_embedding_tasks = []

            for _, row in df.iterrows(): # Create all embedding tasks concurrently.
                all_embedding_tasks.append(loop.run_in_executor(
                    executor, get_emb.get_embeddings, row["image_uri"], row["Description"]
                ))
                all_embedding_tasks.append(loop.run_in_executor(
                    executor, get_emb.get_embeddings, None, row["Description"]
                ))
                all_embedding_tasks.append(loop.run_in_executor(
                    executor, get_emb.get_embeddings, row["image_uri"], None
                ))
            
            all_results = await asyncio.gather(*all_embedding_tasks) # Gather results concurrently

            # Reshape the results to match the order or rows in dataframe
            multimodal_results = all_results[::3]  
            text_results = all_results[1::3]      
            image_results = all_results[2::3]     

            df["multimodal_embeddings"] = multimodal_results
            df["text_embeddings"] = text_results
            df["image_embeddings"] = image_results


        # ... (Load data to AlloyDB - No changes needed)


    except Exception as e:
        # ... (error handling)


# ... (create_embeddings_index function - No changes needed)



# get_emb.py
import logging
import logging.config
import os
import requests
import json

# ... (API endpoint definitions)

logging.config.fileConfig("logging.conf") # Log at module level only, once.
logger = logging.getLogger(__name__)

if "LOG_LEVEL" in os.environ:
    # ... (environment variable handling) - No changes needed
    pass



def get_embeddings(image_uri=None, text=None):  # No lock needed
    # ... (your existing embedding logic)

#...Other functions



# logging.conf
# ... (No changes needed – ensure correct configuration)


