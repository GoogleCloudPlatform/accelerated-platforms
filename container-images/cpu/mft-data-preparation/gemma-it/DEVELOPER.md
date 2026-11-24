# Data Preparation Developer Guide

The data preparation script uses the `datapreparation` module from
[modules/python/src/datapreparation](/modules/python/src/datapreparation). The
unit tests of the module are in
[modules/python/tests/test_datapreparation](/modules/python/tests/test_datapreparation).

## Run the unit tests

- Clone the repository

  ```
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Install the requirements

  ```
  pip install --no-cache-dir -r requirements.txt
  ```

- Run the unit tests

  ```
  bash run_python_unittests.sh
  ```

## Run the script

The script starts a local Ray instance when it isn't submitted to a Ray cluster.

- Install
  [`pyenv`](https://github.com/pyenv/pyenv?tab=readme-ov-file#installation)

- Install the `python` version

  ```
  pyenv install 3.12.16
  ```

- Change directory to the `src` directory

  ```
  cd container-images/cpu/mft-data-preparation/gemma-it/src
  ```

- Set the local `python` version

  ```
  pyenv local 3.12.16
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

- Link the `datapreparation` module, the container image build copies the module
  next to the script

  ```
  ln -s ../../../../../modules/python/src/datapreparation datapreparation
  ```

- Set the application default credentials, they are used to read the processed
  data from and write the prepared dataset to Cloud Storage

  ```
  gcloud auth application-default login
  ```

- Set environment variables

  ```
  export BUCKET="<bucket containing the processed data>"

  export DATASET_INPUT_PATH="flipkart_preprocessed_dataset"
  export DATASET_INPUT_FILE="flipkart.csv"
  export DATASET_OUTPUT_PATH="dataset/output"
  export NUM_QUESTIONS="6"
  export SEED="42"
  ```

- Run the `dataprep.py` script

  ```
  python dataprep.py
  ```

- Remove the link to the `datapreparation` module

  ```
  rm datapreparation
  ```
