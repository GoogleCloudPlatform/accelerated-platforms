### Run benchmarks for inference

We can run inference benchmark on our deployed model using locust.
Locust is an open source performance/load testing tool for HTTP and other protocols.
Refer to the documentation to [set up](https://docs.locust.io/en/stable/installation.html) locust locally or deploy as a container on GKE.

In this example, we will set up locus locally to run tests against our model using sample prompts.



*   Open Cloudshell

*   Install the locust library locally:

    ```sh
    pip3 install locust==2.29.1
    ```

*   Review the file [locus.py](./src/locust.py) to see the prompt being used.

*   Launch the benchmark python script for locust:

    ```sh
    python benchmarks/locust.py $EVAL_MODEL_PATH
    ```

Here is a sample ![graph](./src/locust.jpg) to review.