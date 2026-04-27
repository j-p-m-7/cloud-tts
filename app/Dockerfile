# Use a slim python image optimized for ARM64 (matches your c8g)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies directly (simple for this scale)
RUN pip install --no-cache-dir boto3 requests dotenv

# Copy your script into the container
COPY worker.py .

# Run the script when the container starts
CMD ["python", "worker.py"]
