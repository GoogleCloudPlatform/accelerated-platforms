# Prepared data

These steps walk you through downloading the prepared data from Hugging Face and uploads the data into the data GCS bucket for use within the guide for the respective [use case](/use-cases).

These prereqs were developed to be run on the [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.

Select a path between **Full dataset** and **Smaller dataset (subset)**. The smaller dataset is a quicker way to experience the pipeline, but if it is used for fine-tuning will result in a less than ideal fine-tuned model.

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific to your environment.

- If you would like to use the **Smaller dataset (subset)**, set the variable below.

  ```sh
  DATASET_SUBSET=-subset
  ```

- Download the Hugging Face CLI library

  ```sh
  pip3 install -U "huggingface_hub[cli]==0.26.2"
  ```

- Download the prepared dataset from Hugging Face and copy it into the GCS bucket

  ```sh
  DATAPREP_REPO=gcp-acp/flipkart-dataprep${DATASET_SUBSET}

  ${HOME}/.local/bin/huggingface-cli download --repo-type dataset ${DATAPREP_REPO} --local-dir ./temp

  gcloud storage cp -R ./temp/* \
    gs://${MLP_DATA_BUCKET}/dataset/output && \

  rm -rf ./temp
  ```

  > **NOTE:** Return to the respective use case instructions you were following.
