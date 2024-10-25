### Run benchmarks for inference

The model is ready to run the benchmarks for inference job. We can run few performance tests using locust.
Locust is an open source performance/load testing tool for HTTP and other protocols.
You can refer to the documentation to [set up](https://docs.locust.io/en/stable/installation.html) locust locally or deploy as a container on GKE.

We have created a sample [locustfile](https://docs.locust.io/en/stable/writing-a-locustfile.html) to run tests against our model using sample prompts which we tried earlier in the exercise.
Here is a sample ![graph](./benchmarks/locust.jpg) to review.

- Install the locust library locally:

  ```sh
  pip3 install locust==2.29.1
  ```

- Add the model id to the locust.py file.

  ```sh
   export MODEL_ID =<add-model-id> 
   sed -i -e "s|_MODEL-ID_|${MODEL-ID}|" benchmarks/locust.py
  ```

- Launch the benchmark python script for locust

  ```sh
  benchmarks/locust.py
  ```