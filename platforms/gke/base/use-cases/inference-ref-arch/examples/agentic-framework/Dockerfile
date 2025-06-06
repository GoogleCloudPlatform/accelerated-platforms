# Use a slim Python image for smaller container size
FROM python:3.10-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
# This step is done separately to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
# This copies everything from your project root into /app in the container
# Ensure your 'my_gaming_app' directory and 'static' directory are here
COPY . .

# Cloud Run injects the PORT environment variable.
# Your application must listen on 0.0.0.0:$PORT.
ENV PORT 8080

# Command to run your application using Uvicorn
CMD uvicorn my_gaming_agent.main:app --host 0.0.0.0 --port $PORT

