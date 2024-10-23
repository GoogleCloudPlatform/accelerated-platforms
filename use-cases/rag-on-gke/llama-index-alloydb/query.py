import os
from flask import Flask, request, jsonify
import sqlalchemy

from query_alloydb import AlloyDBNaiveRetriever, AlloyDBNaiveQueryEngine

app = Flask(__name__)


@app.route("/query", methods=["POST"])
def run_query():
    json_req = request.get_json()
    response = query.query(json_req["input"])
    return jsonify(response)


if __name__ == "__main__":
    URL = os.getenv("DB_URL")
    engine = sqlalchemy.create_engine(URL)
    meta_data = sqlalchemy.MetaData()
    meta_data.reflect(bind=engine)
    flipkart = meta_data.tables["flipkart"]
    emb = meta_data.tables["flipkart_multi"]

    subq = (
        sqlalchemy.select(
            flipkart.c.uniq_id,
            flipkart.c.product_name,
            flipkart.c.description,
            flipkart.c.brand,
            flipkart.c.image_uri,
            emb.c.embedding,
        )
        .select_from(flipkart)
        .join(emb, flipkart.c.uniq_id == emb.c.uniq_id)
        .subquery()
    )

    j_retr = AlloyDBNaiveRetriever(
        url="",
        table=subq,
        text_column="description",
        embedding_column="embedding",
        embedding_function="embed_text",
        id_column="uniq_id",
        metadata_columns=["product_name", "brand", "image_uri"],
        db_engine=engine,
    )

    query = AlloyDBNaiveQueryEngine(
        db_engine=engine, retriever=j_retr, llm_function="inference_text"
    )
    app.run(host="0.0.0.0", port=5000)
