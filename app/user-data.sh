#!/bin/bash
# 1. Setup Docker
sudo dnf update -y
sudo dnf install -y docker
sudo systemctl start docker
sudo systemctl enable docker

# 2. Start the Kokoro API Engine
sudo docker run -d \
  --name kokoro-api \
  --restart always \
  -p 8880:8880 \
  ghcr.io/remsky/kokoro-fastapi-cpu:latest

# 3. Start YOUR Worker from GitHub
sudo docker run -d \
  --name tts-worker \
  --restart always \
  --network="host" \
  -e SQS_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/887678038115/tts-queue" \
  ghcr.io/j-p-m-7/tts-worker:latest
