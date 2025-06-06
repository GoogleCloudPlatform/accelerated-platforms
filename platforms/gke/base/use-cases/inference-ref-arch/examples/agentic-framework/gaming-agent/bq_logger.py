import datetime
import json
from google.cloud import bigquery
import vertexai  # Used for initializing Vertex AI if not already done globally

# Import config for constants
from . import config


class BigQueryLogger:
    """
    Manages BigQuery client and logging operations for the gaming agent.
    Ensures dataset and table exist before logging.
    """

    def __init__(self, project_id: str = config.PROJECT_ID,  # Use config.PROJECT_ID as default
                 dataset_id: str = config.BQ_DATASET_ID,     # Use config.BQ_DATASET_ID as default
                 table_id: str = config.BQ_TABLE_ID,         # Use config.BQ_TABLE_ID as default
                 location: str = config.LOCATION):           # Use config.LOCATION as default
        # Initialize Vertex AI globally (needed for other services like GenerativeModel)
        # This ensures vertexai.init() is called once per process.
        vertexai.init(project=project_id, location=location) 

        self._client = bigquery.Client(project=project_id)
        self._dataset_id = dataset_id
        self._table_id = table_id
        self._location = location
        self._table_ref = self._client.dataset(self._dataset_id).table(self._table_id)

        # Ensure table exists when the logger is initialized
        self.ensure_table_exists()

    def ensure_table_exists(self):
        """Ensures the BigQuery dataset and table exist."""
        print(f"\n--- Ensuring BigQuery Dataset and Table Exist ({self._dataset_id}.{self._table_id}) ---")
        try:
            self._client.get_dataset(self._dataset_id)
            print(f"Dataset '{self._dataset_id}' already exists.")
        except Exception:
            print(f"Creating dataset '{self._dataset_id}' in project '{self._client.project}'...")
            dataset = bigquery.Dataset(f"{self._client.project}.{self._dataset_id}")
            dataset.location = self._location
            self._client.create_dataset(dataset, exists_ok=True)
            print(f"Dataset '{self._dataset_id}' created.")

        try:
            self._client.get_table(self._table_ref)
            print(f"Table '{self._table_id}' already exists.")
        except Exception:
            print(f"Creating table '{self._table_id}'...")
            schema = [
                bigquery.SchemaField("log_id", "STRING", mode="REQUIRED",
                                     description="Unique identifier for the log entry."),
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED",
                                     description="UTC timestamp of the log entry."),
                bigquery.SchemaField("agent_name", "STRING", mode="REQUIRED",
                                     description="Name of the agent or tool that performed the action."),
                bigquery.SchemaField("prompt_text_used", "STRING", mode="REQUIRED",
                                     description="The full prompt text used to generate the output."),
                bigquery.SchemaField("generated_dialogues", "STRING", mode="NULLABLE",
                                     description="JSON string of generated NPC dialogues options."),
                bigquery.SchemaField("selected_dialogue", "STRING", mode="NULLABLE",
                                     description="The dialogue option selected by the user."),
                bigquery.SchemaField("image_gcs_path", "STRING", mode="NULLABLE",
                                     description="GCS path(s) to generated images, if applicable (comma-separated for multiple)."),
                bigquery.SchemaField("video_gcs_path", "STRING", mode="NULLABLE",
                                     description="GCS path(s) to generated videos, if applicable (comma-separated for multiple)."),
                bigquery.SchemaField("task_description", "STRING", mode="REQUIRED",
                                     description="Brief description of the task performed."),
            ]
            table = bigquery.Table(self._table_ref, schema=schema)
            self._client.create_table(table)
            print(f"Table '{self._table_id}' created successfully.")

    def log_entry(self, log_id: str, agent_name: str, prompt_text_used: str,
                  generated_dialogues: list = None, selected_dialogue: str = None,
                  image_gcs_path: str = None, video_gcs_path: str = None, task_description: str = None):
        """
        Logs agent outputs to a BigQuery table.
        """
        try:
            # Re-fetch the table object to ensure schema is up-to-date,
            # though generally not strictly needed after ensure_table_exists().
            table = self._client.get_table(self._table_ref)
        except Exception as e:
            print(f"Error fetching table schema for logging: {e}")
            return

        rows_to_insert = [
            {
                "log_id": log_id,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "agent_name": agent_name,
                "prompt_text_used": prompt_text_used,
                "generated_dialogues": json.dumps(generated_dialogues) if generated_dialogues is not None else None,
                "selected_dialogue": selected_dialogue,
                "image_gcs_path": image_gcs_path,
                "video_gcs_path": video_gcs_path,
                "task_description": task_description,
            }
        ]

        try:
            errors = self._client.insert_rows(table, rows_to_insert)
            if errors:
                print(f"Encountered errors while inserting rows: {errors}")
            else:
                print(f"Log entry {log_id} inserted into BigQuery.")
        except Exception as e:
            print(f"Error inserting into BigQuery: {e}")
