FROM python:3.13.0-slim

WORKDIR /app

COPY get_emb.py semantic_search.py rerank.py main.py requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
