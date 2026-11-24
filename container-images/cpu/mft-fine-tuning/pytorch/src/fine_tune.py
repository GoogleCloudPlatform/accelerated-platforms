# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import glob
import logging
import logging.config
import os
import random
import re
import signal
import sys

import datasets
import torch
import torch.distributed as dist
import transformers
from accelerate import Accelerator
from datasets import Dataset, load_dataset, load_from_disk
from peft import LoraConfig, PeftModel
from peft.utils import SAFETENSORS_WEIGHTS_NAME
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainerCallback
from trl import SFTConfig, SFTTrainer

# The folder of a checkpoint that holds the copy of the adapter weights. It is two
# levels below the checkpoint: the trainer loads every folder directly below a
# checkpoint that holds adapter weights as one more adapter.
ADAPTER_CHECKPOINT_FOLDER = os.path.join("fine_tune", "adapter")


class AdapterCheckpointCallback(TrainerCallback):
    """Saves a copy of the adapter weights in every checkpoint.

    The fine-tuning can't resume from the checkpoints of the trainer alone. For a
    model that is distributed with FSDP, the adapter weights of those checkpoints
    are not restored (peft 0.20.0 and later).
    """

    def on_save(self, args, state, control, model=None, **kwargs):
        checkpoint = os.path.join(args.output_dir, f"checkpoint-{state.global_step}")
        # Every process has to call save_pretrained, as the weights are gathered
        # from all of them. Only the main process writes the files.
        model.save_pretrained(
            os.path.join(checkpoint, ADAPTER_CHECKPOINT_FOLDER),
            is_main_process=state.is_world_process_zero,
        )


def adapter_is_trained(model):
    """Whether the LoRA weights of the model differ from their initial values."""
    return any(
        parameter.count_nonzero() > 0
        for name, parameter in model.named_parameters()
        if "lora_B" in name
    )


def get_resumable_checkpoint(model_path):
    """Returns the newest checkpoint that has a copy of the adapter weights."""
    checkpoints = {}
    for path in glob.glob(f"{model_path}/checkpoint-*"):
        match = re.fullmatch(r"checkpoint-(\d+)", os.path.basename(path))
        if match:
            checkpoints[int(match.group(1))] = path
    for step in sorted(checkpoints, reverse=True):
        adapter_weights = os.path.join(
            checkpoints[step], ADAPTER_CHECKPOINT_FOLDER, SAFETENSORS_WEIGHTS_NAME
        )
        if os.path.isfile(adapter_weights):
            return checkpoints[step]
        logger.warning(
            f"Ignoring the checkpoint {checkpoints[step]}, it has no copy of the adapter weights"
        )
    return None


def graceful_shutdown(signal_number, stack_frame):
    signal_name = signal.Signals(signal_number).name

    logger.info(f"Received {signal_name}({signal_number}), shutting down...")
    # TODO: Add logic to handled checkpointing if required
    sys.exit(0)


def formatting_prompts_func(example):
    prompts = []
    completions = []
    for i in range(len(example["prompt"])):
        text = f"""{example["prompt"][i]}\n{EOS_TOKEN}"""
        # The model is fine-tuned to generate the text after the delimiter
        prompt, delimiter, completion = text.partition(INPUT_OUTPUT_DELIMITER)
        prompts.append(f"{prompt}{delimiter}")
        completions.append(completion)
    return {"prompt": prompts, "completion": completions}


def get_current_node_id_and_rank():
    if dist.is_initialized():
        logger.info("Distributed training enabled.")
        logger.info("Calculating node id")
        global_rank = dist.get_rank()  # Get the process's rank
        logger.info(f"global_rank: {global_rank}")
        gpu_per_node = torch.cuda.device_count()
        logger.info(f"gpu_per_node: {gpu_per_node}")
        total_gpus = accelerator.state.num_processes
        logger.info(f"total_gpus: {total_gpus}")
        total_nodes = int(total_gpus / gpu_per_node)
        logger.info(f"total_nodes: {total_nodes}")
        node_id = global_rank // gpu_per_node
    else:
        logger.info("Distributed training enabled.")
        node_id = 0
        global_rank = 0
    logger.info(f"node_id: {node_id}")
    return (node_id, global_rank, gpu_per_node)


if __name__ == "__main__":
    # Configure logging
    logging.config.fileConfig("logging.conf")
    logger = logging.getLogger("finetune")

    if "LOG_LEVEL" in os.environ:
        new_log_level = os.environ["LOG_LEVEL"].upper()
        logger.info(
            f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
        )
        logging.getLogger().setLevel(new_log_level)
        logger.setLevel(new_log_level)

    datasets.disable_progress_bar()
    transformers.utils.logging.disable_progress_bar()

    logger.info("Configure signal handlers")
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    accelerator = Accelerator()

    # The integrations to report the results and logs to
    report_to = "none"

    if "MLFLOW_ENABLE" in os.environ and os.environ["MLFLOW_ENABLE"] == "true":
        import mlflow

        remote_server_uri = os.environ["MLFLOW_TRACKING_URI"]
        mlflow.set_tracking_uri(remote_server_uri)

        experiment_name = os.environ["EXPERIMENT"]
        if accelerator.is_main_process:  # Only the main process sets the experiment
            # Check if the experiment already exists
            experiment = mlflow.get_experiment_by_name(experiment_name)
            if experiment is None:
                # Experiment doesn't exist, create it
                try:
                    experiment_id = mlflow.create_experiment(experiment_name)
                    experiment = mlflow.get_experiment(experiment_id)
                    print(
                        f"Created new experiment: {experiment.name} (ID: {experiment.experiment_id})"
                    )
                except Exception as ex:
                    logger.error(f"Create experiment failed: {ex}")
            else:
                # Experiment already exists, use it
                logger.info(
                    f"Using existing experiment: {experiment.name} (ID: {experiment.experiment_id})"
                )

        # Barrier to ensure all processes wait until the experiment is created
        accelerator.wait_for_everyone()
        experiment = mlflow.get_experiment_by_name(experiment_name)

        # Get the node ID
        node, rank, gpu_per_node = get_current_node_id_and_rank()
        node_id = "node_" + str(node)
        logger.info(f"Training at: {node_id} process: {rank}")
        process_id = "process_" + str(rank)

        # Set MLflow experiment and node ID (within the appropriate run context)
        mlflow.set_experiment(experiment_name)
        mlflow.set_system_metrics_node_id(node_id)

        # Check and create/reuse runs
        # Only one process per node creates a run to capture system metrics
        if (rank % gpu_per_node) == 0:
            existing_run = mlflow.search_runs(
                experiment_ids=[experiment.experiment_id],
                filter_string=f"tags.mlflow.runName = '{process_id}'",
            )
            # No existing run with this name
            if len(existing_run) == 0:
                run = mlflow.start_run(
                    run_name=node_id,
                    experiment_id=experiment.experiment_id,
                )
                has_active_ml_flow_run = True
            else:
                logger.info(f"Run with name '{process_id}' already exists")
                client = mlflow.MlflowClient()
                data = client.get_run(mlflow.active_run().info.run_id).data
                logger.info(f"Active run details: '{data}'")

        # logging of model parameters, metrics, and artifacts
        mlflow.autolog()
        report_to = "mlflow"

    # The bucket which contains the training data
    training_data_bucket = os.environ["TRAINING_DATASET_BUCKET"]

    training_data_path = os.environ["TRAINING_DATASET_PATH"]

    # The model that you want to train from the Hugging Face hub
    model_name = os.environ["MODEL_NAME"]

    # Fine-tuned model name
    new_model = os.environ["NEW_MODEL"]

    # The root path of where the fine-tuned model will be saved
    save_model_path = os.environ["MODEL_PATH"]

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"  # Fix weird overflow issue with fp16 training

    EOS_TOKEN = tokenizer.eos_token

    training_dataset = load_from_disk(
        f"gs://{training_data_bucket}/{training_data_path}"
    )

    INPUT_OUTPUT_DELIMITER = "<start_of_turn>model"

    logger.info("Data Formatting Started")
    input_data = training_dataset.map(
        formatting_prompts_func,
        batched=True,
        remove_columns=training_dataset.column_names,
    )
    logger.info("Data Formatting Completed")

    ################################################################################
    # QLoRA parameters
    ################################################################################

    # LoRA attention dimension
    lora_r = int(os.getenv("LORA_R", "8"))

    # Alpha parameter for LoRA scaling
    lora_alpha = int(os.getenv("LORA_ALPHA", "16"))

    # Dropout probability for LoRA layers
    lora_dropout = float(os.getenv("LORA_DROPOUT", "0.1"))

    ################################################################################
    # TrainingArguments parameters
    ################################################################################

    # Output directory where the model predictions and checkpoints will be stored
    # output_dir = "./results"

    # Number of training epochs
    num_train_epochs = int(os.getenv("EPOCHS", "1"))

    # Enable fp16/bf16 training (set bf16 to True with an A100)
    fp16 = False
    bf16 = False

    # Batch size per GPU for training
    per_device_train_batch_size = int(os.getenv("TRAIN_BATCH_SIZE", "1"))

    # Batch size per GPU for evaluation
    per_device_eval_batch_size = 1

    # Number of update steps to accumulate the gradients for
    gradient_accumulation_steps = int(os.getenv("GRADIENT_ACCUMULATION_STEPS", "1"))

    # Enable gradient checkpointing
    gradient_checkpointing = True

    # Maximum gradient normal (gradient clipping)
    max_grad_norm = float(os.getenv("MAX_GRAD_NORM", "0.3"))

    # Initial learning rate (AdamW optimizer)
    learning_rate = float(os.getenv("LEARNING_RATE", "2e-4"))

    # Weight decay to apply to all layers except bias/LayerNorm weights
    weight_decay = float(os.getenv("WEIGHT_DECAY", "0.001"))

    # Optimizer to use
    optim = "adamw_torch"

    # Learning rate schedule
    lr_scheduler_type = "cosine"

    # Number of training steps (overrides num_train_epochs)
    max_steps = -1

    # Ratio of steps for a linear warmup (from 0 to learning rate)
    warmup_ratio = float(os.getenv("WARMUP_RATIO", "0.03"))

    # Group sequences into batches with same length
    # Saves memory and speeds up training considerably
    train_sampling_strategy = "group_by_length"

    # Save strategy: steps, epoch, no
    save_strategy = os.getenv("CHECKPOINT_SAVE_STRATEGY", "steps")

    # Save total limit of checkpoints
    save_total_limit = int(os.getenv("CHECKPOINT_SAVE_TOTAL_LIMIT", "5"))

    # Save checkpoint every X updates steps
    save_steps = int(os.getenv("CHECKPOINT_SAVE_STEPS", "1000"))

    # Log every X updates steps
    logging_steps = 50

    ################################################################################
    # SFT parameters
    ################################################################################

    # Maximum sequence length to use
    max_seq_length = int(os.getenv("MAX_SEQ_LENGTH", "512"))

    # Pack multiple short examples in the same input sequence to increase efficiency
    packing = False

    # Load base model
    logger.info("Loading base model started")
    model = AutoModelForCausalLM.from_pretrained(
        attn_implementation="eager",
        dtype=torch.bfloat16,
        pretrained_model_name_or_path=model_name,
    )
    model.config.use_cache = False
    model.config.pretraining_tp = 1
    logger.info("Loading base model completed")

    logger.info("Configuring fine tuning started")
    # Load LoRA configuration
    peft_config = LoraConfig(
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        r=lora_r,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )

    # Set training parameters
    training_arguments = SFTConfig(
        bf16=bf16,
        completion_only_loss=True,  # Fine-tune on the completions of the prompts
        disable_tqdm=True,
        fp16=fp16,
        gradient_accumulation_steps=gradient_accumulation_steps,
        gradient_checkpointing=gradient_checkpointing,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        log_on_each_node=False,
        logging_steps=logging_steps,
        learning_rate=learning_rate,
        lr_scheduler_type=lr_scheduler_type,
        max_grad_norm=max_grad_norm,
        max_length=max_seq_length,
        max_steps=max_steps,
        num_train_epochs=num_train_epochs,
        optim=optim,
        output_dir=save_model_path,
        packing=packing,
        per_device_train_batch_size=per_device_train_batch_size,
        report_to=report_to,
        save_strategy=save_strategy,
        save_steps=save_steps,
        save_total_limit=save_total_limit,
        train_sampling_strategy=train_sampling_strategy,
        warmup_steps=warmup_ratio,  # A value below 1 is a ratio of the training steps
        weight_decay=weight_decay,
    )
    logger.info("Configuring fine tuning completed")

    logger.info("Creating trainer started")
    trainer = SFTTrainer(
        args=training_arguments,
        callbacks=[AdapterCheckpointCallback()],
        model=model,
        peft_config=peft_config,
        processing_class=tokenizer,
        train_dataset=input_data,
    )
    logger.info("Creating trainer completed")

    logger.info("Fine tuning started")
    # Resume from the newest checkpoint, when there is one
    checkpoint = get_resumable_checkpoint(save_model_path)
    if checkpoint is not None:
        logger.info(f"Resuming from the checkpoint {checkpoint}")
        # The adapter weights are loaded before the trainer distributes the model
        load_result = trainer.model.load_adapter(
            os.path.join(checkpoint, ADAPTER_CHECKPOINT_FOLDER),
            adapter_name=trainer.model.active_adapter,
            is_trainable=True,
        )
        if load_result.unexpected_keys or not adapter_is_trained(trainer.model):
            raise RuntimeError(
                f"The adapter weights of the checkpoint {checkpoint} were not restored"
            )
    trainer.train(resume_from_checkpoint=checkpoint)
    logger.info("Fine tuning completed")

    if "MLFLOW_ENABLE" in os.environ and os.environ["MLFLOW_ENABLE"] == "true":
        if accelerator.is_main_process:  # register the model only at main process
            mv = mlflow.register_model(
                model_uri=f"gs://{training_data_bucket}/{save_model_path}",
                name=new_model,
            )
            logger.info(f"Name: {mv.name}")
            logger.info(f"Version: {mv.version}")

    logger.info("Saving new model started")
    trainer.model.save_pretrained(new_model)
    logger.info("Saving new model completed")

    logger.info("Merging the new model with base model started")
    # Reload model in FP16 and merge it with LoRA weights
    base_model = AutoModelForCausalLM.from_pretrained(
        dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
        pretrained_model_name_or_path=model_name,
        return_dict=True,
    )
    model = PeftModel.from_pretrained(
        model=base_model,
        model_id=new_model,
    )
    # Without this check, a model without the fine-tuning would be saved
    if not adapter_is_trained(model):
        raise RuntimeError(
            f"The adapter that was saved in '{new_model}' has no fine-tuned weights"
        )
    model = model.merge_and_unload()
    logger.info("Merging the new model with base model completed")

    logger.info("Accelerate unwrap model started")
    unwrapped_model = accelerator.unwrap_model(model)
    logger.info("Accelerate unwrap model completed")

    logger.info("Save unwrapped model started")
    unwrapped_model.save_pretrained(
        is_main_process=accelerator.is_main_process,
        save_directory=save_model_path,
    )
    logger.info("Save unwrapped model completed")

    logger.info("Save new tokenizer started")
    if accelerator.is_main_process:
        tokenizer.save_pretrained(save_model_path)
    logger.info("Save new tokenizer completed")

    # Barrier to ensure all processes wait until 'unwrapped model save' is completed
    accelerator.wait_for_everyone()

    logger.info("Script completed")
