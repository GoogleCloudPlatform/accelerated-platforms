FROM python:3.10-slim

# # Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy the model.py script
COPY model.py /app/model.py

# Expose the port that the app will run on
EXPOSE 5000

# Start the server
CMD ["python", "/app/model.py"]