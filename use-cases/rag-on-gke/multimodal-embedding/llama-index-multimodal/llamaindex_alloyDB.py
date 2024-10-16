from sqlalchemy import create_engine
from llama_index import SQLDatabase, ServiceContext, LLMPredictor, PromptHelper
from llama_index.indices.vector_store.faiss import FaissIndex
from langchain.chat_models import ChatOpenAI

# Create the AlloyDB connection string
# Note: Replace the placeholders with your actual AlloyDB credentials
connection_string = "postgresql+psycopg2://<username>:<password>@<hostname>:<port>/<database>"

# Create the SQLAlchemy engine
engine = create_engine(connection_string)

# Define the SQL tables you want to use
tables = ["your_table_name"]

# Create the SQLDatabase object
sql_database = SQLDatabase(engine, include_tables=tables)

# Configure LLM and PromptHelper
llm_predictor = LLMPredictor(llm=ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo"))
prompt_helper = PromptHelper(max_input_size=4096, num_output=256, max_chunk_overlap=20)

# Create the FaissIndex
service_context = ServiceContext.from_defaults(llm_predictor=llm_predictor, prompt_helper=prompt_helper)
index = FaissIndex.from_documents(sql_database.get_documents(), service_context=service_context)

# Now you can query the index
query_engine = index.as_query_engine()
response = query_engine.query("your_query_here")

print(response)