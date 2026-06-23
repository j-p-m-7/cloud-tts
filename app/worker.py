import json
import logging
import os
import sys
import time
from datetime import datetime

import boto3
import requests
from botocore.exceptions import ClientError

# logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
)

# config
INPUT_BUCKET = "tts-pipeline-input"
OUTPUT_BUCKET = "tts-pipeline-output"
LOGS_BUCKET = "tts-pipeline-output"
API_URL = "http://localhost:8880/v1/audio/speech"
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")

if not SQS_QUEUE_URL:
    logging.critical(
        "CRITICAL CONFIGURATION ERROR: SQS_QUEUE_URL environment variable is missing."
    )
    sys.exit(1)

# aws instance metadata (IMDSv2)
INSTANCE_TYPE = "local-test-instance"
INSTANCE_COST_PER_HR = 0.00000

try:
    logging.info("querying...")
    token_headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
    token_res = requests.put(
        "http://169.254.169.254/latest/api/token", headers=token_headers, timeout=2
    )

    if token_res.status_code == 200:
        metadata_headers = {"X-aws-ec2-metadata-token": token_res.text}
        INSTANCE_TYPE = requests.get(
            "http://169.254.169.254/latest/meta-data/instance-type",
            headers=metadata_headers,
            timeout=2,
        ).text

        # pricing
        if "c8g.xlarge" in INSTANCE_TYPE:
            INSTANCE_COST_PER_HR = 0.15952
        elif "c8g.2xlarge" in INSTANCE_TYPE:
            INSTANCE_COST_PER_HR = 0.31904
        else:
            INSTANCE_COST_PER_HR = 0.16000

        logging.info(f"AWS Instance Type: {INSTANCE_TYPE}")
except (requests.exceptions.RequestException, Exception) as imds_error:
    logging.warning(f"IMDSv2 query failed ({imds_error}).")

# initalize aws sdk clients
try:
    sqs = boto3.client("sqs", region_name="us-east-1")
    s3 = boto3.client("s3", region_name="us-east-1")
except Exception as init_error:
    logging.critical(f"Failed to initialize AWS clients: {init_error}")
    sys.exit(1)


def process_worker():
    logging.info(
        f" Worker Online | Instance: {INSTANCE_TYPE} | Polling: {SQS_QUEUE_URL}"
    )

    # get message from sqs
    while True:
        try:
            response = sqs.receive_message(
                QueueUrl=SQS_QUEUE_URL, MaxNumberOfMessages=1, WaitTimeSeconds=20
            )
        except ClientError as ce:
            logging.error(
                f"Failed to poll SQS due to ClientError: {ce}. Backing off for 30s..."
            )
            time.sleep(30)
            continue

        if "Messages" not in response:
            logging.debug("SQS Poll returned empty. Continuing long poll...")
            continue

        msg = response["Messages"][0]
        book_key = msg["Body"]
        receipt_handle = msg["ReceiptHandle"]

        try:
            logging.info(f" Processing task: {book_key}")

            # pull text from s3
            try:
                text_obj = s3.get_object(Bucket=INPUT_BUCKET, Key=book_key)
                content = text_obj["Body"].read().decode("utf-8")
                word_count = len(content.split())
            except ClientError as s3_error:
                logging.error(
                    f"S3 download failed for {book_key}: {s3_error}. Releasing task back to SQS/DLQ pipeline."
                )
                _release_message(receipt_handle)
                continue

            # make tts request
            start_time = time.time()
            try:
                res = requests.post(
                    API_URL,
                    json={
                        "input": content,
                        "voice": "af_heart",
                        "response_format": "mp3",
                    },
                    timeout=600,
                )
                res.raise_for_status()
            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
            ) as http_net_error:
                logging.error(
                    f"TTS Engine connection/timeout error on {book_key}: {http_net_error}. Releasing task."
                )
                _release_message(receipt_handle)
                continue
            except requests.exceptions.HTTPError as http_status_error:
                logging.error(
                    f"TTS Engine rejected processing request (Status {res.status_code}): {http_status_error}. Abandoning task to DLQ."
                )
                continue

            duration = time.time() - start_time

            # upload audio output to s3
            output_key = book_key.replace("books/", "audio/").replace(".txt", ".mp3")
            s3.put_object(Bucket=OUTPUT_BUCKET, Key=output_key, Body=res.content)

            # calculate metrics
            est_audio_mins = word_count / 150
            rtf = est_audio_mins / (duration / 60)
            cost_usd = (duration / 3600) * INSTANCE_COST_PER_HR

            # log metrics
            log_data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "instance_type": INSTANCE_TYPE,
                "book": book_key,
                "word_count": word_count,
                "processing_time_sec": round(duration, 2),
                "rtf": round(rtf, 2),
                "cost_usd": f"{cost_usd:.6f}",
            }

            log_key = book_key.replace("books/", "logs/").replace(".txt", ".json")
            s3.put_object(Bucket=LOGS_BUCKET, Key=log_key, Body=json.dumps(log_data))

            # remove processed item from sqs queue
            sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
            logging.info(
                f" Successfully finished {book_key} | RTF: {rtf:.2f}x | Cost: ${cost_usd:.5f}"
            )

        except Exception as unhandled_pipeline_error:
            logging.critical(
                f"Unhandled operational crisis while executing task {book_key}: {unhandled_pipeline_error}"
            )
            _release_message(receipt_handle)


def _release_message(receipt_handle):
    """Resets message visibility to 0 to safely return it to the queue for retry/DLQ ingestion."""
    try:
        sqs.change_message_visibility(
            QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle, VisibilityTimeout=0
        )
        logging.info(
            "Message tracking visibility reset to 0; immediately available for secondary workers."
        )
    except ClientError as vis_error:
        logging.error(
            f"Failed to cleanly modify SQS message visibility layer: {vis_error}"
        )


if __name__ == "__main__":
    process_worker()
