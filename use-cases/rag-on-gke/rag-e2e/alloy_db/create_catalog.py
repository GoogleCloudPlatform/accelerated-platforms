# import sqlalchemy
# from google.cloud.alloydb.connector import Connector
from sqlalchemy import create_engine
from google.cloud import alloydb_v1 as alloydb
from typing import Tuple
import psycopg2
import pandas as pd


def create_database(host, database, user, password, new_database_name):
    """Creates a new database in PostgreSQL using psycopg2."""

    try:
        # Connect to an existing database (e.g., 'postgres')
        conn = psycopg2.connect(
            host=host, database=database, user=user, password=password
        )

        conn.autocommit = True  # Enable autocommit mode

        # Create a cursor object
        cursor = conn.cursor()

        # Execute the CREATE DATABASE command
        cursor.execute(f"CREATE DATABASE {new_database_name}")

        print(f"Database '{new_database_name}' created successfully.")

    except Exception as e:
        print(f"Error creating database: {e}")

    finally:
        # Close the cursor and connection
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def create_and_populate_table(
    host, database, user, password, table_name, processed_data_path
):
    """
    Creates and populates a table in PostgreSQL using pandas and sqlalchemy.
    """

    try:
        # Connect to the database using sqlalchemy
        engine = create_engine(f"postgresql://{user}:{password}@{host}/{database}")

        # Load the CSV into a Pandas DataFrame
        df = pd.read_csv(processed_data_path)

        # Use to_sql to insert data into the database
        df.to_sql(table_name, engine, if_exists="replace", index=False)

        print(f"Table '{table_name}' created and populated successfully.")

    except psycopg2.Error as e:
        print(f"PostgreSQL error: {e}")
        # Handle specific PostgreSQL errors (e.g., unique constraint violation)
        if e.pgcode == "23505":
            print("Error: Duplicate key value violates unique constraint.")

    except pd.errors.EmptyDataError:
        print("Error: Input CSV file is empty.")

    except FileNotFoundError:
        print(f"Error: CSV file not found at {processed_data_path}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
