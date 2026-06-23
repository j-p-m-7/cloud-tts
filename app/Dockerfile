FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir boto3 requests dotenv
COPY worker.py .
CMD ["python", "worker.py"]
