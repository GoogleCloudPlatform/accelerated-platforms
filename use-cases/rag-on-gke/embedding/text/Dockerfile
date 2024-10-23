FROM continuumio/miniconda3:23.3.1-0

# Install OpenCV3 Python bindings
#RUN sudo apt-get update

# Create a working directory
#RUN mkdir /app

# Add requirements file
WORKDIR /app/
ADD requirements.txt /app/

# Install requirements

RUN pip install -r requirements.txt

# Download Sentence Transformers Model
RUN python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ.get('model_name', 'bert-base-nli-stsb-mean-tokens'));"

# Move required resources
ADD app.py   /app/

# Run flask api
ENTRYPOINT ["python"]
CMD ["app.py"]
