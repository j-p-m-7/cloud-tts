import boto3
import requests
import time
import json
import os
from datetime import datetime

# CONFIGURATION
INSTANCE_TYPE = "c8g.xlarge"
INSTANCE_COST_PER_HR = 0.15952
INPUT_BUCKET = "tts-pipeline-input"
OUTPUT_BUCKET = "tts-pipeline-output"
LOGS_BUCKET = "tts-pipeline-output"
API_URL = "http://localhost:8880/v1/audio/speech"
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")

sqs = boto3.client('sqs', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')

def process_worker():
    print(f"🚀 Worker Online | {INSTANCE_TYPE} | Polling SQS...")

    while True:
        response = sqs.receive_message(
            QueueUrl=SQS_QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20
        )

        if 'Messages' not in response:
            continue

        msg = response['Messages'][0]
        book_key = msg['Body']
        receipt_handle = msg['ReceiptHandle']

        try:
            # 1. Download Text
            text_obj = s3.get_object(Bucket=INPUT_BUCKET, Key=book_key)
            content = text_obj['Body'].read().decode('utf-8')
            word_count = len(content.split())

            # 2. Synthesis & Timing
            start_time = time.time()
            res = requests.post(API_URL, json={
                "input": content, "voice": "af_heart", "response_format": "mp3"
            }, timeout=600)
            duration = time.time() - start_time

            if res.status_code == 200:
                # 3. Upload Audio
                output_key = book_key.replace("books/", "audio/").replace(".txt", ".mp3")
                s3.put_object(Bucket=OUTPUT_BUCKET, Key=output_key, Body=res.content)

                # 4. CALCULATE METRICS
                # Assuming 150 words per minute of audio
                est_audio_mins = word_count / 150
                rtf = est_audio_mins / (duration / 60)
                # Cost for this specific book
                cost_usd = (duration / 3600) * INSTANCE_COST_PER_HR

                # 5. LOG TO S3
                log_data = {
                    "timestamp": datetime.now().isoformat(),
                    "instance_type": INSTANCE_TYPE,
                    "book": book_key,
                    "word_count": word_count,
                    "processing_time_sec": round(duration, 2),
                    "rtf": round(rtf, 2),
                    "cost_usd": f"{cost_usd:.6f}"
                }

                log_key = book_key.replace("books/", "logs/").replace(".txt", ".json")
                s3.put_object(
                    Bucket=LOGS_BUCKET,
                    Key=log_key,
                    Body=json.dumps(log_data)
                )

                # 6. Delete from Queue
                sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
                print(f"✅ Finished {book_key} | RTF: {rtf:.2f}x | Cost: ${cost_usd:.5f}")

        except Exception as e:
            print(f"⚠️ Error: {str(e)}")

if __name__ == "__main__":
    process_worker()
