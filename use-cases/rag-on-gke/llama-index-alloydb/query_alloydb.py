"""Naive llama_index query and retrieve class for AlloyDB"""

from typing import List, Union, Callable
from llama_index.core import PromptTemplate
from llama_index.core.query_engine import CustomQueryEngine
from llama_index.core.schema import QueryBundle, NodeWithScore, TextNode
from llama_index.core.retrievers import BaseRetriever
from pgvector.sqlalchemy import Vector
from pydantic import PrivateAttr
import sqlalchemy
from sqlalchemy.sql.selectable import Subquery, Select


class AlloyDBNaiveRetriever(BaseRetriever):
    """Retriever for AlloyDB with ml functions."""

    label_of_distance = "distance_941ed738"

    def __init__(
        self,
        url: str,
        table: Union[str, Subquery],
        text_column: str,
        embedding_column: str,
        embedding_function: Union[str, Callable],
        id_column: str,
        metadata_columns: List[str],
        table_schema: str = "public",
        similarity_top_k: int = 5,
        db_engine: sqlalchemy.Engine = None,
    ):
        self._similarity_top_k = similarity_top_k
        if db_engine:
            self._db_engine = db_engine
        else:
            self._db_engine = sqlalchemy.create_engine(url)

        self._db_meta_data = sqlalchemy.MetaData()
        if isinstance(table, str):
            self._db_meta_data.reflect(bind=self._db_engine, schema=table_schema)
            self._db_table = self._db_meta_data.tables[f"{table_schema}.{table}"]
        else:
            self._db_table = table
        self._table_embedding_column = self._db_table.c[embedding_column]
        self._text_column = text_column
        self._metadata_columns = metadata_columns
        self._id_column = id_column
        self._table_all_columns = [
            self._db_table.c[x]
            for x in set([text_column] + metadata_columns + [id_column])
        ]

        if isinstance(embedding_function, str):
            self._embedding_function = lambda *x: sqlalchemy.Function(
                embedding_function, *x, type_=Vector
            )
        else:
            self._embedding_function = embedding_function
        self._db_connection = self._db_engine.connect()
        super().__init__()

    def _row_to_nodewithscore(self, row):
        metadata = {}
        for k in self._metadata_columns:
            metadata[k] = getattr(row, k)
        node = TextNode(
            text=getattr(row, self._text_column),
            metadata=metadata,
            id_=getattr(row, self._id_column),
        )
        score = 1 - getattr(row, self.label_of_distance)
        return NodeWithScore(node=node, score=score)

    def _as_sql(self, query_bundle: QueryBundle) -> Select:
        """Retrieve as a sql query."""
        embed_func = self._embedding_function(query_bundle.query_str)
        distance_column = self._table_embedding_column.l2_distance(embed_func).label(
            self.label_of_distance
        )
        columns = self._table_all_columns + [distance_column]
        stmt = (
            sqlalchemy.select(*columns)
            .order_by(distance_column)
            .limit(self._similarity_top_k)
        )
        return stmt

    def as_subquery(self, query_bundle_or_str: Union[str, QueryBundle]) -> Subquery:
        """Get the SQL subquery for this retriever."""
        if isinstance(query_bundle_or_str, str):
            stmt = self._as_sql(QueryBundle(query_bundle_or_str))
        else:
            stmt = self._as_sql(query_bundle_or_str)
        subq = stmt.subquery()
        return (
            sqlalchemy.select(
                sqlalchemy.func.string_agg(subq.c[self._text_column], "\n").label(
                    "context"
                )
            )
            .select_from(subq)
            .subquery()
        )

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Retrieve."""
        stmt = self._as_sql(query_bundle)
        results = self._db_connection.execute(stmt)
        return [self._row_to_nodewithscore(r) for r in results]


class AlloyDBNaiveQueryEngine(CustomQueryEngine):
    retriever: AlloyDBNaiveRetriever
    qa_prompt: PromptTemplate = PromptTemplate(
        "Context information is below.\n"
        "---------------------\n"
        "{context_str}\n"
        "---------------------\n"
        "Given the context information and not prior knowledge, "
        "answer the query.\n"
        "Query: {query_str}\n"
        "Answer: "
    )
    db_engine: sqlalchemy.Engine
    _inference_func: Callable
    _db_connection: sqlalchemy.engine.base.Connection

    def __init__(self, llm_function: Union[str, Callable], **kwargs):
        super().__init__(**kwargs)
        if isinstance(llm_function, str):
            self._inference_func = lambda *x: sqlalchemy.Function(llm_function, *x)
        else:
            self._inference_func = self.llm_function
        self._db_connection = self.db_engine.connect()

    def _synth_sql(self, query_str: str) -> Select:
        subq = self.retriever.as_subquery(query_str)
        prompt = self.qa_prompt.format(query_str=query_str, context_str="%1$s")
        stmt = sqlalchemy.select(
            self._inference_func(sqlalchemy.func.format(prompt, subq.c.context))
        ).select_from(subq)
        return stmt

    def custom_query(self, query_str: str):
        stmt = self._synth_sql(query_str)
        results = self._db_connection.execute(stmt)
        res, *_ = results.fetchone()
        return res


def get_flipkart_table(url):
    engine = sqlalchemy.create_engine(url)
    meta_data = sqlalchemy.MetaData()
    meta_data.reflect(bind=engine)
    flipkart = meta_data.tables["flipkart"]
    emb = meta_data.tables["flipkart_embeded"]

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
    return subq


def test_joined_table(url):
    engine = sqlalchemy.create_engine(url)
    subq = get_flipkart_table(url)
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
    jnodes = j_retr.retrieve("cycling shorts")
    for nn in jnodes:
        print(nn)
    query = AlloyDBNaiveQueryEngine(
        db_engine=engine, retriever=j_retr, llm_function="vllm_completion"
    )
    response = query.query("cycling shorts for women")
    print(str(response))


if __name__ == "__main__":
    import os

    dburl = os.getenv("PGURL")
    test_retriever = AlloyDBNaiveRetriever(
        url=dburl,
        table="flipkart_embeded",
        text_column="uniq_id",
        embedding_column="embedding",
        embedding_function="embed_text",
        id_column="uniq_id",
        metadata_columns=[],
    )
    nodes = test_retriever.retrieve("cycling shorts")
    for n in nodes:
        print(n)
    test_joined_table(dburl)
