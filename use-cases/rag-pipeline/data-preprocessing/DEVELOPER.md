# Distributed Data Processing Developer Guide

- Install [`pyenv`](https://github.com/pyenv/pyenv?tab=readme-ov-file#installation)

- Install the `python` version

  ```
  pyenv install 3.12.8
  ```

- Clone the repository

  ```
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the `src` directory

  ```
  cd use-cases/rag-pipeline/data-preprocessing/src
  ```

- Copy python modules to the current directory

  ```
  cp -r ${MLP_BASE_DIR}/modules/python/src/datapreprocessing .
  ```

- Set the local `python` version

  ```
  pyenv local 3.12.8
  ```

- Create a virtual environment

  ```
  python -m venv venv
  ```

- Activate the virtual environment

  ```
  source venv/bin/activate
  ```

- Install the requirements

  ```
  pip install --no-cache-dir -r requirements.txt
  ```

- Set the Ray Cluster to run locally

  ```
  export RAY_CLUSTER_HOST=local
  ```

- Set the project for the GCS storage bucket

  ```
  gcloud config set project ${MLP_PROJECT_ID}
  ```

- Set the GCS storage bucket name

  ```
  export PROCESSING_BUCKET=
  ```

- Run the `preprocessing_rag.py` script

  ```
  python preprocessing_rag.py
  ```
