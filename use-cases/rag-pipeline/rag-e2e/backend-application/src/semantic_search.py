from get_emb import *
import json
from sqlalchemy import text

import logging

logging.basicConfig(level=logging.INFO)


# TODO: only text input from UI is handled. Need to add image uri to get embeddings
def find_matching_products(
    engine,
    user_query,
    catalog_table,
    embedding_column,
    row_count,
):
    try:
        # Get text embedding for user query
        user_query_emb = json.dumps(get_text_embeddings(user_query))
        # logging.info(user_query_emb)

        # TODO: Add a function call to get image embedding if image uri (gs://)
        # image_emb = json.dumps(get_image_embeddings(image_uri))
        # TODO: if both text & image were given call multimodal embedding
        # image_emb = json.dumps(get_multimodal_embeddings(image, text))

        # Parameterized query
        search_query = f"""SELECT "Name", "Description", "c1_name" as Category, "Specifications", (1-({embedding_column} <-> :emb)) AS cosine_similarity FROM {catalog_table} ORDER BY cosine_similarity DESC LIMIT {row_count};"""
        logging.info(search_query)

        # Execute the query with the embedding as a parameter
        with engine.connect() as conn:
            # Perform a cosine similarity search
            result = conn.execute(
                text(search_query),
                {"emb": user_query_emb},
            )

            # logging.info(result)
            response = [row._asdict() for row in result]
            logging.info(response)
            # String format the retrieved information
            retrieved_information = "\n".join(
                [
                    f"{index+1}. "
                    + "\n".join([f"{key}: {value}" for key, value in element.items()])
                    for index, element in enumerate(response)
                ]
            )
        logging.info(retrieved_information)
        return retrieved_information

    except Exception as e:
        logging.error(f"An error occurred while finding matching products: {e}")
    finally:
        if conn:
            conn.close()
