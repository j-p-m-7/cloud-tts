import boto3

# Configuration - CHANGE THESE
REGION = 'us-east-1'
BUCKET_NAME = 'tts-pipeline-input'
PREFIX = 'books/gutenberg/'
QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/887678038115/tts-queue'

# Explicitly set the region here
s3 = boto3.client('s3', region_name=REGION)
sqs = boto3.client('sqs', region_name=REGION)


def populate_queue():
    paginator = s3.get_paginator('list_objects_v2')
    entries = []

    print(f"Scanning s3://{BUCKET_NAME}/{PREFIX}...")

    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=PREFIX):
        if 'Contents' in page:
            for obj in page['Contents']:
                file_key = obj['Key']

                if file_key.endswith('.txt'):
                    # Prepare batch entry
                    entries.append({
                        'Id': str(len(entries)), # Required unique ID per batch
                        'MessageBody': file_key
                    })

                    # SQS send_message_batch supports max 10 messages
                    if len(entries) == 10:
                        sqs.send_message_batch(QueueUrl=QUEUE_URL, Entries=entries)
                        print(f"Sent batch of 10...")
                        entries = []

    # Send any remaining messages
    if entries:
        sqs.send_message_batch(QueueUrl=QUEUE_URL, Entries=entries)
        print(f"Sent final batch of {len(entries)}.")

if __name__ == "__main__":
    populate_queue()
