
import json
import os
from typing import List
from urllib import request
import gradio as gr
import sqlalchemy

from query_alloydb import (AlloyDBNaiveRetriever,
                           AlloyDBNaieveLLM,
                           get_flipkart_table)
from llama_index.core.schema import NodeWithScore


PROMPT_TEMPL = (
    "Context information is below.\n"
    "---------------\n"
    "{context_str}\n"
    "---------------\n"
    "Given the context information and not "
    "prior knowledge, answer the query:\n"
    "Query: which is the best fit for {query_str}\n"
    "Answer:\n"
)


class GemmaRunner:
    llm: AlloyDBNaieveLLM
    retr: AlloyDBNaiveRetriever

    def __init__(self, llm, retr):
        self.llm = llm
        self.retr = retr

    def generate_prompt(self,
                        nodes: List[NodeWithScore],
                        prompt_templ: str,
                        query_str: str):
        context = "\n".join(f"""{n.text}.""" for n in nodes)
        return prompt_templ.format(context_str=context,
                                   query_str=query_str)

    def run_query(self, query, prompt_templ):
        nodes = self.retr.retrieve(query)
        prompt = self.generate_prompt(nodes, prompt_templ, query)
        response = self.llm.complete(prompt)
        return prompt, str(response)


class FTAgentRunner:
    llm: AlloyDBNaieveLLM
    retr: AlloyDBNaiveRetriever

    def __init__(self, llm, retr):
        self.llm = llm
        self.retr = retr

    def generate_prompt(self,
                        nodes: List[NodeWithScore],
                        query_str: str):
        prompt_templ = (
        "Product description: {context_str}\n"
        )
        context = nodes[0].text
        return prompt_templ.format(context_str=context,
                                   query_str=query_str)

    def run_query(self, query):
        nodes = self.retr.retrieve(query)
        output = "# Iterative query\n"
        output += ("\nThe 5 products are fetched from similarity"
                   " search using cosing distance.")
        for n in nodes:
            prompt = self.generate_prompt([n], query)
            response = self.llm.complete(prompt)
            output += "\n## Node: \n\n"
            output += f"```\n{str(n)}\n```\n"
            output += "\n### Prompt:\n\n" + prompt
            output += "\n### Answer from vLLM:\n\n" + str(response)

        return output

def generate_db_url_from_workload_identity():
    urlbase = ("http://metadata.google.internal/"
               "computeMetadata/v1/instance/"
               "service-accounts/default/")
    req = request.Request(urlbase + "email",
                          headers={"Metadata-Flavor" :
                                   "Google"})
    rr = request.urlopen(req)
    email = rr.read().decode("utf8")
    rr.close()
    pguser = email.removesuffix(".gserviceaccount.com")
    req = request.Request(urlbase + "token",
                          headers={"Metadata-Flavor" :
                                   "Google"})
    rr = request.urlopen(req)
    t = json.load(rr)
    rr.close()
    pgpassword = t["access_token"]
    pghost = os.getenv("PGHOST")
    pgdatabase = os.getenv("PGDATABASE")
    return sqlalchemy.engine.URL.create("postgresql+psycopg",
                                        username=pguser,
                                        password=pgpassword,
                                        host=pghost,
                                        database=pgdatabase)


if __name__ == "__main__":
    URL=os.getenv("DB_URL")
    if not URL:
        URL = generate_db_url_from_workload_identity()
    engine = sqlalchemy.create_engine(URL)
    subq = get_flipkart_table(URL)
    j_retr = AlloyDBNaiveRetriever(url="",
                                   table= subq,
                                   text_column="description",
                                   embedding_column="embedding",
                                   embedding_function=
                                   "google_ml.embedding_text",
                                   id_column="uniq_id",
                                   metadata_columns=["product_name",
                                                     "brand",
                                                     "image_uri"],
                                   db_engine=engine
                                   )

    gemma_llm = AlloyDBNaieveLLM(llm_function="gemma2_completion",
                                 db_engine=engine)

    ft_llm = AlloyDBNaieveLLM(llm_function="vllm_completion",
                              db_engine=engine)
    gemma_runner = GemmaRunner(llm=gemma_llm, retr=j_retr)
    ft_runner = FTAgentRunner(llm=ft_llm, retr=j_retr)
    gemma_if = gr.Interface(
        fn=gemma_runner.run_query,
        inputs=[gr.Textbox(label="Your question",
                           info="Put your ask here:"),
                gr.Textbox(label="Prompt template",
                           info="the template for generating the prompt",
                           value=PROMPT_TEMPL)],
        outputs=[gr.Textbox(label="The prompt"),
                 gr.Textbox(label="The answer")],
        allow_flagging="never"
    )
    ft_if = gr.Interface(
        fn=ft_runner.run_query,
        inputs=["text"],
        outputs=gr.Markdown(label="Products found:", height=1000),
        allow_flagging="never"
    )
    demo = gr.TabbedInterface([ft_if, gemma_if],
                              ["Chat with Finetuned model",
                               "Chat with Gemma2"])
    demo.launch(server_name = "0.0.0.0",
        server_port = 8000)
