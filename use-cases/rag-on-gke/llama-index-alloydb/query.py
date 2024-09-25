
import os
import gradio as gr
import sqlalchemy

from query_alloydb import AlloyDBNaiveRetriever, AlloyDBNaiveQueryEngine, get_flipkart_table


def run_query(prompt):
    response = query.query(prompt)
    return response

if __name__ == "__main__":
    URL=os.getenv("DB_URL")
    engine = sqlalchemy.create_engine(URL)
    subq = get_flipkart_table(URL)
    j_retr = AlloyDBNaiveRetriever(url="",
                                   table= subq,
                                   text_column="description",
                                   embedding_column="embedding",
                                   embedding_function="google_ml.embedding_text",
                                   id_column="uniq_id",
                                   metadata_columns=["product_name",
                                                     "brand",
                                                     "image_uri"],
                                   db_engine=engine
                                   )

    query = AlloyDBNaiveQueryEngine(db_engine=engine,
                                    retriever = j_retr,
                                    llm_function = "vllm_completion")

    demo = gr.Interface(
        fn=run_query,
        inputs=["text"],
        outputs=["text"]
    )
    demo.launch()
