# --- STAGE 1: Build Stage ---
# Use a Python image that includes tools for installing dependencies
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_HOME /usr/src/app

# Create and set the working directory
WORKDIR $APP_HOME

# Copy only the requirements file first to leverage Docker cache
COPY --from=primary requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# --- STAGE 2: Final Runtime Stage ---
# Use a minimal runtime image for security and size
FROM python:3.11-slim

# Set environment variables for the runtime
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_HOME /usr/src/app

# Create and set the working directory
WORKDIR $APP_HOME

# Copy installed dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application script itself
COPY --from=primary app.py .

# Command to run the application when the container starts
CMD ["python", "app.py"]
