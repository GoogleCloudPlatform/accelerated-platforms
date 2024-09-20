from locust import FastHttpUser, task, between

model_id = "/data/models/model-gemma2-a100/experiment-a2aa2c3it1"

message1 = (
    "I'm looking for comfortable cycling shorts for women, what are some good options?"
)
message2 = "Tell me about some tops for men, looking for different styles"


class TestUser(FastHttpUser):
    wait_time = between(1, 5)

    @task(50)
    def test1(self):
        self.client.post(
            "/v1/chat/completions",
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": message1}],
                "temperature": 0.5,
                "top_k": 1.0,
                "top_p": 1.0,
                "max_tokens": 256,
            },
            name="message1",
        )

    @task(50)
    def test2(self):
        self.client.post(
            "/v1/chat/completions",
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": message2}],
                "temperature": 0.5,
                "top_k": 1.0,
                "top_p": 1.0,
                "max_tokens": 256,
            },
            name="message2",
        )
