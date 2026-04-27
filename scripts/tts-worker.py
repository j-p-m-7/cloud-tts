import boto3
import requests
import time
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# ==========================================================
# CONFIGURATION
# ==========================================================

SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")

if not SQS_QUEUE_URL:
    print("ERROR: SQS_QUEUE_URL environment variable is not set.")
    sys.exit(1)

# S3 Buckets (Separated as per your report logic)
INPUT_BUCKET = "tts-pipeline-input"
OUTPUT_BUCKET = "tts-pipeline-output"

# Local API (The Kokoro Docker container)
API_URL = "http://localhost:8880/v1/audio/speech"

# Initialize Clients
sqs = boto3.client('sqs', region_name='us-east-1')
s3 = boto3.client('s3')

def run_single_test():
    print(f"🚀 Initializing Test Worker...")
    print(f"📡 Polling: {SQS_QUEUE_URL}")

    # 1. Ask SQS for exactly ONE message
    response = sqs.receive_message(
        QueueUrl=SQS_QUEUE_URL,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=10,
        VisibilityTimeout=300 # 5 mins is plenty for 1 book test
    )

    messages = response.get('Messages', [])
    if not messages:
        print("Empty Queue: No message found to process. Exiting.")
        return

    msg = messages[0]
    receipt_handle = msg['ReceiptHandle']
    book_key = msg['Body'] # Expecting "books/gutenberg/1.txt"

    # Generate Output Path: books/gutenberg/1.txt -> audio/gutenberg/1.mp3
    output_key = book_key.replace("books/", "audio/").replace(".txt", ".mp3")

    try:
        print(f"📥 Found Task: {book_key}")

        # 2. Pull Text Content from S3
        print(f"📖 Downloading text from S3...")
        text_obj = s3.get_object(Bucket=INPUT_BUCKET, Key=book_key)
        content = text_obj['Body'].read().decode('utf-8')

        # 3. Send to Kokoro API
        print(f"🎙️ Generating Speech (this may take a minute)...")
        start_time = time.time()

        res = requests.post(API_URL, json={
            "input": content,
            "voice": "af_heart",
            "response_format": "mp3"
        }, timeout=600)

        if res.status_code == 200:
            duration = time.time() - start_time
            print(f"✨ Synthesis Complete in {duration:.2f}s")

            # 4. Upload Result to Output Bucket
            print(f"📤 Uploading to s3://{OUTPUT_BUCKET}/{output_key}")
            s3.put_object(
                Bucket=OUTPUT_BUCKET,
                Key=output_key,
                Body=res.content,
                ContentType='audio/mpeg'
            )

            # 5. Cleanup SQS
            sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
            print(f"✅ Success! Message deleted from queue.")
        else:
            print(f"❌ API Error ({res.status_code}): {res.text}")

    except Exception as e:
        print(f"⚠️ Test Failed: {str(e)}")

if __name__ == "__main__":
    run_single_test()
