# Distributed TTS Pipeline

A cloud-native, distributed text-to-speech pipeline for converting public-domain books from [Project Gutenberg](https://www.gutenberg.org/) into audiobooks using parallel processing across multiple compute nodes on AWS.

See [architecture.md](architecture.md) for the full system design and C4 diagrams.

## Project Structure

```
├── architecture.md              # system architecture doc (C1/C2 diagrams, component descriptions)
├── scripts/
│   └── gutenberg_to_s3.py       # proof-of-concept: gutenberg → s3 ingestion
├── requirements.txt             # python dependencies
└── README.md
```

## Prerequisites

- Python 3.10+
- An AWS account with programmatic access (access key id + secret access key)
- AWS CLI

### Install AWS CLI (macOS)

```bash
brew install awscli
```

### Configure AWS credentials

We need an **access key**, not the console login password. To create one:

1. Log into the [AWS console](https://console.aws.amazon.com/) as a root or admin user
2. Go to **IAM** > **Users** > select the target user > **Security credentials**
3. Under **Access keys**, click **Create access key**
4. Copy the access key id and secret access key

Then configure your local machine:

```bash
aws configure
```

It will prompt for:
- **AWS Access Key ID**
- **AWS Secret Access Key**
- **Default region name:** `us-east-1`
- **Default output format:** `json`

### Set up Python environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Scripts

### `scripts/gutenberg_to_s3.py`

Proof-of-concept for the ingestion step of the pipeline. Downloads a plain-text book from Project Gutenberg, uploads it to an S3 bucket, and verifies the round-trip by reading it back.

**What it does:**

1. Fetches a book's plain text from `gutenberg.org/cache/epub/<id>/pg<id>.txt`
2. Creates an S3 bucket (`tts-pipeline-input`) if it doesn't exist
3. Uploads the text to `s3://tts-pipeline-input/books/gutenberg/<id>.txt`
4. Reads the object back from S3 and verifies the content matches
5. Lists all objects in the bucket

**Usage:**

```bash
source venv/bin/activate

# default book (gutenberg id 164)
python scripts/gutenberg_to_s3.py

# specify a different book
python scripts/gutenberg_to_s3.py --book-id 1342

# custom bucket name and region
python scripts/gutenberg_to_s3.py --bucket my-bucket --region us-west-2
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--book-id` | `164` | Gutenberg book ID |
| `--bucket` | `tts-pipeline-input` | S3 bucket name |
| `--region` | `us-east-1` | AWS region |

You can browse available books at [gutenberg.org](https://www.gutenberg.org/).
