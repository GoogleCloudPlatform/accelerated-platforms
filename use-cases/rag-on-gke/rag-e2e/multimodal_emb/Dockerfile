#FROM pytorch/pytorch:2.0.0-cuda11.7-cudnn8-runtime
FROM pytorch/pytorch:2.5.0-cuda12.4-cudnn9-runtime

# Copy your Python script
COPY embedding.py requirements.txt /app/

# Set the working directory
WORKDIR /app

# Install necessary libraries
RUN pip install -r requirements.txt
RUN pip install --force-reinstall -v "numpy==1.26.4"

# Command to run your script
CMD ["python", "embedding.py"]