FROM python:3.13.0-slim-bookworm

WORKDIR /workspace

COPY requirements.txt /workspace/

RUN pip install --no-cache-dir -r /workspace/requirements.txt

COPY logging.conf \ 
    interface.py \
    /workspace/

ENV PYTHONUNBUFFERED 1

EXPOSE 7860

CMD ["python3", "interface.py"]

