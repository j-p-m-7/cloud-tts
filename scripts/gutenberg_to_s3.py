"""
proof-of-concept script for the distributed tts pipeline.

downloads a plain-text book from project gutenberg, uploads it to an s3
bucket, and verifies the round-trip by reading it back. this validates the
first leg of the pipeline: ingesting source texts into cloud object storage.

prerequisites:
    - aws credentials configured via `aws configure`
    - python dependencies installed (boto3, requests)

usage:
    python scripts/gutenberg_to_s3.py
    python scripts/gutenberg_to_s3.py --book-id 1342       # pride and prejudice
    python scripts/gutenberg_to_s3.py --book-id 2701       # moby dick
    python scripts/gutenberg_to_s3.py --bucket my-bucket    # custom bucket name
    python scripts/gutenberg_to_s3.py --region us-west-2    # custom region
"""

import argparse
import sys

import boto3
import requests
from botocore.exceptions import ClientError

# gutenberg exposes plain-text mirrors at predictable urls keyed by book id
GUTENBERG_PLAIN_TEXT_URL = "https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"

DEFAULT_BUCKET_NAME = "tts-pipeline-input"
DEFAULT_REGION = "us-east-1"
DEFAULT_BOOK_ID = 164  # https://www.gutenberg.org/ebooks/164


def download_book(book_id: int) -> str:
    """fetch a single book's plain-text content from project gutenberg by its id.

    gutenberg assigns each book a numeric id. the plain-text version is served
    from a predictable url pattern under /cache/epub/.

    args:
        book_id: the gutenberg catalog id (e.g. 1342 for pride and prejudice).

    returns:
        the full text of the book as a string.

    raises:
        requests.HTTPError: if the book id doesn't exist or gutenberg is unreachable.
    """
    url = GUTENBERG_PLAIN_TEXT_URL.format(book_id=book_id)
    print(f"Downloading book {book_id} from {url} ...")

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    text = resp.text
    print(f"  Downloaded {len(text):,} characters ({len(text.split()):,} words)")
    return text


def ensure_bucket_exists(s3_client, bucket_name: str, region: str) -> None:
    """create the s3 bucket if it doesn't already exist.

    uses head_bucket to check existence. if the bucket is missing (404),
    creates it in the specified region. us-east-1 is a special case in the
    aws api — it doesn't accept a LocationConstraint.

    args:
        s3_client: a boto3 s3 client.
        bucket_name: the name of the bucket to ensure exists.
        region: the aws region to create the bucket in if needed.

    raises:
        ClientError: if the bucket check fails for a reason other than 404.
    """
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' already exists.")
    except ClientError as e:
        error_code = int(e.response["Error"]["Code"])
        if error_code == 404:
            print(f"Creating bucket '{bucket_name}' in {region} ...")
            if region == "us-east-1":
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": region},
                )
            print(f"  Bucket created.")
        else:
            raise


def upload_to_s3(s3_client, bucket_name: str, key: str, text: str) -> None:
    """upload a utf-8 text string to s3 as a plain-text object.

    args:
        s3_client: a boto3 s3 client.
        bucket_name: the target s3 bucket.
        key: the s3 object key (e.g. "books/gutenberg/1342.txt").
        text: the text content to upload.
    """
    print(f"Uploading to s3://{bucket_name}/{key} ...")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=text.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
    )
    print(f"  Upload complete.")


def verify_upload(s3_client, bucket_name: str, key: str, original_text: str) -> bool:
    """read the object back from s3 and compare it to the original text.

    this is a simple integrity check to confirm the upload was lossless.

    args:
        s3_client: a boto3 s3 client.
        bucket_name: the s3 bucket to read from.
        key: the s3 object key to read.
        original_text: the expected text content.

    returns:
        true if the downloaded content matches the original, false otherwise.
    """
    print(f"Verifying round-trip by reading back s3://{bucket_name}/{key} ...")
    resp = s3_client.get_object(Bucket=bucket_name, Key=key)
    downloaded = resp["Body"].read().decode("utf-8")

    if downloaded == original_text:
        print(f"  Round-trip verified: {len(downloaded):,} characters match.")
        return True
    else:
        print(f"  MISMATCH: uploaded {len(original_text):,} chars, got back {len(downloaded):,} chars")
        return False


def print_preview(text: str, lines: int = 10) -> None:
    """print the first n lines of a text string for a quick sanity check."""
    print(f"\n--- First {lines} lines of the book ---")
    for line in text.splitlines()[:lines]:
        print(f"  {line}")
    print("---\n")


def list_bucket_contents(s3_client, bucket_name: str) -> None:
    """list all objects currently stored in the bucket with their sizes."""
    print(f"\nContents of s3://{bucket_name}/:")
    resp = s3_client.list_objects_v2(Bucket=bucket_name)
    if "Contents" not in resp:
        print("  (empty)")
        return
    for obj in resp["Contents"]:
        size_kb = obj["Size"] / 1024
        print(f"  {obj['Key']:60s}  {size_kb:>8.1f} KB")


def main():
    """entry point. parses cli args and runs the full gutenberg-to-s3 flow."""
    parser = argparse.ArgumentParser(description="download a gutenberg book and upload it to s3")
    parser.add_argument("--book-id", type=int, default=DEFAULT_BOOK_ID, help=f"gutenberg book id (default: {DEFAULT_BOOK_ID})")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET_NAME, help=f"s3 bucket name (default: {DEFAULT_BUCKET_NAME})")
    parser.add_argument("--region", default=DEFAULT_REGION, help=f"aws region (default: {DEFAULT_REGION})")
    args = parser.parse_args()

    print("=" * 60)
    print("  Gutenberg → S3 Proof of Concept")
    print("=" * 60)
    print()

    # step 1: download book from gutenberg
    text = download_book(args.book_id)
    print_preview(text)

    # step 2: set up s3 client and ensure bucket exists
    s3_client = boto3.client("s3", region_name=args.region)
    ensure_bucket_exists(s3_client, args.bucket, args.region)

    # step 3: upload book text to s3 under books/gutenberg/<id>.txt
    s3_key = f"books/gutenberg/{args.book_id}.txt"
    upload_to_s3(s3_client, args.bucket, s3_key, text)

    # step 4: read it back and verify integrity
    verified = verify_upload(s3_client, args.bucket, s3_key, text)

    # step 5: show what's in the bucket now
    list_bucket_contents(s3_client, args.bucket)

    print()
    if verified:
        print("Book successfully downloaded from Gutenberg and stored in S3.")
    else:
        print("Failed.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
