import logging
import os
import pathlib
import sys
import time

import boto3
import requests
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
if not SQS_QUEUE_URL:
    logging.error("SQS_QUEUE_URL environment variable is not set.")
    sys.exit(1)

INPUT_BUCKET = "tts-pipeline-input"
OUTPUT_BUCKET = "tts-pipeline-output"
API_URL = "http://localhost:8880/v1/audio/speech"

sqs = boto3.client("sqs", region_name="us-east-1")
s3 = boto3.client("s3", region_name="us-east-1")


def run_single_test():
    logging.info("🚀 Initializing Test Worker...")

    try:
        response = sqs.receive_message(
            QueueUrl=SQS_QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10,
            VisibilityTimeout=300,
        )
    except ClientError as e:
        logging.error(f"Failed to poll SQS: {e}")
        return

    messages = response.get("Messages", [])
    if not messages:
        logging.info("Empty Queue: No message found to process. Exiting.")
        return

    msg = messages[0]
    receipt_handle = msg["ReceiptHandle"]
    book_key = msg["Body"]

    # Robust path building using pathlib
    pure_path = pathlib.PurePosixPath(book_key)
    # Replaces the root 'books' with 'audio' safely, regardless of substrings
    relative_parts = pure_path.relative_to("books")
    output_key = str(
        pathlib.PurePosixPath("audio") / relative_parts.with_suffix(".mp3")
    )

    try:
        logging.info(f"📥 Found Task: {book_key}")

        # 2. Extract
        logging.info("📖 Downloading text from S3...")
        text_obj = s3.get_object(Bucket=INPUT_BUCKET, Key=book_key)
        content = text_obj["Body"].read().decode("utf-8")

        # 3. Transform (Synthesis)
        logging.info("🎙️ Requesting compute from Kokoro API Engine...")
        start_time = time.time()

        res = requests.post(
            API_URL,
            json={"input": content, "voice": "af_heart", "response_format": "mp3"},
            timeout=300,
        )  # Reduced to 5 mins for realistic unit tests

        if res.status_code != 200:
            raise requests.exceptions.HTTPError(
                f"API Error ({res.status_code}): {res.text}"
            )

        duration = time.time() - start_time
        logging.info(f"✨ Synthesis Complete in {duration:.2f}s")

        # 4. Load
        logging.info(f"📤 Uploading payload to s3://{OUTPUT_BUCKET}/{output_key}")
        s3.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=output_key,
            Body=res.content,
            ContentType="audio/mpeg",
        )

        # 5. Commit/Acknowledge
        sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
        logging.info("✅ Success! Task completed and message removed from SQS.")

    except Exception as pipeline_error:
        logging.error(f"⚠️ Test Execution Failed: {pipeline_error}")

        # RESILIENCY PATTERN: Change visibility timeout back to 0 so
        # another worker or test instance can retry processing immediately.
        try:
            logging.info(
                "🔄 Backing off: Returning message to queue immediately for re-processing..."
            )
            sqs.change_message_visibility(
                QueueUrl=SQS_QUEUE_URL,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=0,
            )
        except ClientError as visibility_error:
            logging.error(
                f"Critical error resetting message tracking state: {visibility_error}"
            )


if __name__ == "__main__":
    run_single_test()
