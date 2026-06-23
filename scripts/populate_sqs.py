import logging
import os
import sys

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

# Setup structured logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

REGION = "us-east-1"
BUCKET_NAME = "tts-pipeline-input"
PREFIX = "books/gutenberg/"
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")

if not SQS_QUEUE_URL:
    logging.error("SQS_QUEUE_URL environment variable is not set.")
    sys.exit(1)

s3 = boto3.client("s3", region_name=REGION)
sqs = boto3.client("sqs", region_name=REGION)


def populate_queue():
    paginator = s3.get_paginator("list_objects_v2")
    entries = []
    batch_count = 0

    logging.info(f"Scanning s3://{BUCKET_NAME}/{PREFIX}...")

    try:
        for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=PREFIX):
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                file_key = obj["Key"]

                if file_key.endswith(".txt"):
                    # Use unique string hash or token instead of index string for Id resiliency
                    entries.append(
                        {
                            "Id": f"msg_{batch_count}_{len(entries)}",
                            "MessageBody": file_key,
                        }
                    )

                    if len(entries) == 10:
                        _send_batch_safely(entries)
                        batch_count += 1
                        entries = []

        if entries:
            _send_batch_safely(entries)

    except ClientError as e:
        logging.error(f"AWS API Ingestion Failure: {e}")
    except Exception as e:
        logging.error(f"Unexpected operational error: {e}")


def _send_batch_safely(batch_entries):
    """Handles SQS batch verification to protect against partial network drops."""
    try:
        response = sqs.send_message_batch(QueueUrl=SQS_QUEUE_URL, Entries=batch_entries)

        # Check for partial failures within the successful HTTP response
        if "Failed" in response and response["Failed"]:
            for failure in response["Failed"]:
                logging.warning(
                    f"Message ID {failure['Id']} failed ingestion. Code: {failure['Code']}"
                )
        else:
            logging.info(
                f"Successfully enqueued batch of {len(batch_entries)} entries."
            )

    except ClientError as ce:
        logging.error(f"Network transport level batch failure: {ce}")


if __name__ == "__main__":
    populate_queue()
