FROM pytorch/pytorch:2.0.0-cuda11.7-cudnn8-runtime

# Copy your Python script
COPY blip2_script.py requirements.txt /app/

# Set the working directory
WORKDIR /app

# Install necessary libraries
RUN pip install -r requirements.txt
#RUN pip install transformers accelerate bitsandbytes pillow

# Command to run your script
CMD ["python", "blip2_script.py"]
