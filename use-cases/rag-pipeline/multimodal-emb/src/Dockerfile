FROM pytorch/pytorch:2.5.0-cuda12.4-cudnn9-runtime

RUN apt-get update && \
    apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Copy your Python script
COPY embedding.py requirements.txt /app/

# Set the working directory
WORKDIR /app

# Install necessary libraries
RUN pip install -r requirements.txt

# Command to run your script
CMD ["python", "embedding.py"]
