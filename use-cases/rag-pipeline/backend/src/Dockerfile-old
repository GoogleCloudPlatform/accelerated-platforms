# FROM python:3.12.7-slim-bookworm

# RUN apt-get update && \
#     apt-get -y --no-install-recommends install python3-dev gcc python3-pip git && \
#     rm -rf /var/lib/apt/lists/*

# COPY requirements.txt /

# RUN pip3 install --no-cache-dir -r /requirements.txt

# COPY backend_service.py /

# ENV PYTHONUNBUFFERED 1

# CMD python3 /backend_service.py


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

