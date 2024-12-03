FROM python:3.13.0-slim-bookworm

WORKDIR /workspace

COPY requirements.txt /workspace/

RUN pip install --no-cache-dir -r /workspace/requirements.txt

COPY backend_service.py \ 
    custom_json_formatter.py \
    generate_embeddings.py \
    logging.conf \
    prompt_helper.py  \
    rerank.py \
    semantic_search.py \
    /workspace/

ENV PYTHONUNBUFFERED 1

CMD ["python", "backend_service.py"]

