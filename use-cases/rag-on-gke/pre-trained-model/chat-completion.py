from typing import List, Optional

import fire
from transformers import AutoTokenizer, AutoModelForCausalLM

def main(
    ckpt_dir: str ="google/gemma2-2b",
    tokenizer_path: str ="google/gemma2-2b",
    temperature: float = 0.6,
    top_p: float = 0.9,
    max_seq_len: int = 512,
    max_batch_size: int = 8,
    max_gen_len: Optional[int] = None,
):
    """
    Entry point of the program for generating text using a pretrained model.

    Args:
        ckpt_dir (str): The directory containing checkpoint files for the pretrained model.
        tokenizer_path (str): The path to the tokenizer model.
        temperature (float): The temperature for sampling.
        top_p (float): The top-p value for nucleus sampling.
        max_seq_len (int): The maximum sequence length.
        max_batch_size (int): The maximum batch size.
        max_gen_len (Optional[int]): The maximum length of the generated text.
    """

    # Initialize the tokenizer and model
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
    model = AutoModelForCausalLM.from_pretrained(ckpt_dir)

    # Create a chat completion function
    def chat_completion(
        messages: List[dict],
        temperature: float = temperature,
        top_p: float = top_p,
        max_gen_len: Optional[int] = max_gen_len,
    ) -> str:
        """
        Generates a chat completion response.

        Args:
            messages (List[dict]): A list of messages in the chat history.
            temperature (float): The temperature for sampling.
            top_p (float): The top-p value for nucleus sampling.
            max_gen_len (Optional[int]): The maximum length of the generated text.

        Returns:
            str: The generated chat completion response.
        """

        # Format the messages into a single prompt string
        prompt = ""
        for message in messages:
            role = message["role"]
            content = message["content"]
            prompt += f"{role}: {content}\n"

        # Generate a response
        inputs = tokenizer(prompt, return_tensors="pt")
        outputs = model.generate(
            inputs.input_ids,
            max_length=max_seq_len,
            temperature=temperature,
            top_p=top_p,
            do_sample=True,
        )
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)

        return response

    # Start the chat loop
    while True:
        user_input = input("User: ")
        messages = [{"role": "user", "content": user_input}]
        response = chat_completion(messages)
        print(f"Gemma: {response}")

if __name__ == "__main__":
    fire.Fire(main)