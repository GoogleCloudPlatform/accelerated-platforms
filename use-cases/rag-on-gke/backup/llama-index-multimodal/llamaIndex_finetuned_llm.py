from typing import Optional, List, Mapping, Any

import requests
import json
from llama_index.core import SimpleDirectoryReader, SummaryIndex
from llama_index.core.callbacks import CallbackManager
from llama_index.core.llms import (
    CustomLLM,
    CompletionResponse,
    CompletionResponseGen,
    LLMMetadata,
)
from llama_index.core.llms.callbacks import llm_completion_callback
from llama_index.core import Settings


class OurLLM(CustomLLM):
    context_window: int = 3900
    num_output: int = 256
    model_name: str = "" # Replace with your model_name
    llm_endpoint: str = ""  # Replace with your actual URL


    @property
    def metadata(self) -> LLMMetadata:
        """Get LLM metadata."""
        return LLMMetadata(
            context_window=self.context_window,
            num_output=self.num_output,
            model_name=self.model_name,
            llm_endpoint=self.llm_endpoint,
        )

    @llm_completion_callback()
    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        response = requests.post(
            url=self.llm_endpoint, json={
                "model": self.model_name,
                "max_tokens": self.num_output,
                "temperature": 0,
                "top_p": 1,
                "messages" : [{"role": "user", "content": prompt}],
                "stream": False}  # Adjust payload if needed
        )
        text = response.json()["choices"][0]["message"]["content"]
        # Adjust based on your API's response format
        return CompletionResponse(text=text)

    @llm_completion_callback()
    def stream_complete(
        self, prompt: str, **kwargs: Any
    ) -> CompletionResponseGen:
        response = requests.post(
            self.llm_endpoint, json={"prompt": prompt, "stream": True}  # Adjust payload if needed
        )
        for chunk in response.iter_lines():
            if chunk:
                decoded_chunk = chunk.decode("utf-8")
                # Assuming your API streams responses with a "text" key
                text_chunk = json.loads(decoded_chunk)["text"]
                yield CompletionResponse(text=text_chunk)


# define our LLM
Settings.llm = OurLLM()

# define embed model
Settings.embed_model = "local:BAAI/bge-base-en-v1.5"


# Load the your data
documents = SimpleDirectoryReader("./data").load_data()
index = SummaryIndex.from_documents(documents)

# Query and print response
query_engine = index.as_query_engine()
response = query_engine.query("I'm looking for comfortable cycling shorts for women, what are some good options?")
print(response)
