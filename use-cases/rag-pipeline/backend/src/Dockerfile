FROM python:3.13.0-slim-bookworm

WORKDIR /workspace

COPY requirements.txt /workspace/

RUN pip install --no-cache-dir -r /workspace/requirements.txt

COPY custom_json_formatter.py \
    generate_embeddings.py \
    logging.conf \
    main.py  \
    rerank.py \
    semantic_search.py \
    /workspace/

ENV PYTHONUNBUFFERED 1

CMD ["python", "backend_service.py"]

