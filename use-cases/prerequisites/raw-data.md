# Raw data for data processing

These steps walk you through downloading the raw data from Kaggle or Hugging
Face and uploads the data into the data GCS bucket for use within the guide for
the respective [use case](/use-cases).

These prereqs were developed to be run on the
[playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you
are using a different environment the scripts and manifest will need to be
modified for that environment.

Select a path between **Full dataset** and **Smaller dataset (subset)**. The
smaller dataset is a quicker way to experience the pipeline, but if it is used
for fine-tuning will result in a less than ideal fine-tuned model.

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific
  > to your environment.

- **Full dataset** Download the raw data CSV file from
  [Kaggle](https://kaggle.com) and store it into the bucket created in the
  previous step.

  - You will need kaggle cli to download the file. The kaggle cli can be
    installed using the following command in Cloud Shell:

    ```sh
    pip3 install --user kaggle
    ```

    For more details, you can read those
    [instructions](https://github.com/Kaggle/kaggle-api#installation).

  - To use the cli you must create an API token. To create the token, register
    on [kaggle.com](https://kaggle.com) if you already don't have an account. Go
    to `kaggle.com/settings > API > Create New Token`, the downloaded file
    should be stored in `$HOME/.kaggle/kaggle.json`. Note, you will have to
    create the dir `$HOME/.kaggle`. After the configuration is done, you can run
    the following command to download the dataset and copy it to the GCS bucket:

    ```sh
    kaggle datasets download --unzip PromptCloudHQ/flipkart-products && \

    gcloud storage cp flipkart_com-ecommerce_sample.csv \
      gs://${MLP_DATA_BUCKET}/flipkart_raw_dataset/flipkart_com-ecommerce_sample.csv && \

    rm flipkart_com-ecommerce_sample.csv
    ```

  - Alternatively, you can
    [downloaded the dataset](https://www.kaggle.com/datasets/PromptCloudHQ/flipkart-products)
    directly from the kaggle website and copy it to the bucket.

- **Smaller dataset (subset)** Download the raw data CSV from Hugging Face.

  - Download the Hugging Face CLI library

    ```sh
    pip3 install -U "huggingface_hub[cli]==0.27.1"
    ```

  - Download the preprocessed dataset CSV file from Hugging Face and copy it
    into the GCS bucket

    ```sh
    RAW_DATA_REPO=gcp-acp/flipkart-raw-subset

    ${HOME}/.local/bin/huggingface-cli download --repo-type dataset ${RAW_DATA_REPO} --local-dir ./temp

    gcloud storage cp ./temp/flipkart_com-ecommerce_sample.csv \
      gs://${MLP_DATA_BUCKET}/flipkart_raw_dataset/flipkart_com-ecommerce_sample.csv && \

    rm ./temp/flipkart_com-ecommerce_sample.csv
    ```

> **NOTE:** Return to the respective use case instructions you were following.
