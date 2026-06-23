#!/bin/bash
# setup docker
sudo dnf update -y
sudo dnf install -y docker
sudo systemctl start docker
sudo systemctl enable docker

# start kokoro api container
sudo docker run -d \
  --name kokoro-api \
  --restart always \
  -p 8880:8880 \
  ghcr.io/remsky/kokoro-fastapi-cpu:latest

# start tts workers
sudo docker run -d \
  --name tts-worker \
  --restart always \
  --network="host" \
  -e SQS_QUEUE_URL="${aws_sqs_queue.tts_queue.url}" \
  ghcr.io/j-p-m-7/tts-worker:latest
