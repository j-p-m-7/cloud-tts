Here is a succinct, highly scannable, and modern version of the `README.md` that highlights your infrastructure improvements without the fluff.

---

# Distributed TTS Pipeline

A cloud-native, distributed text-to-speech (TTS) pipeline that parallelizes the conversion of public-domain books from [Project Gutenberg](https://www.gutenberg.org/) into audiobooks using an elastic compute fleet on AWS.

See [architecture.md](architecture.md) for detailed C4 design diagrams and tradeoffs.

## Project Structure

```
├── app/                        # Worker container ecosystem
│   ├── Dockerfile              # ARM64 optimized worker image
│   └── worker.py               # Core processing daemon with IMDSv2 telemetry
├── terraform/                  # Infrastructure as Code (IaC)
│   ├── main.tf                 # S3 Storage & SQS/DLQ messaging layers
│   ├── asg.tf                  # EC2 Auto Scaling Group & user-data scripts
│   └── iam.tf                  # Least-privilege IAM roles and profiles
├── scripts/                    # Ingestion & analytics tooling
│   ├── gutenberg_to_s3.py      # Gutenberg text ingestion engine
│   └── populate_sqs.py         # SQS safe batch processing script
└── requirements.txt            # Python core dependencies

```

---

## Quick Start

### 1. Configure AWS & Environment

Ensure you have the AWS CLI installed and configured with programmatic access credentials:

```bash
aws configure
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt

```

### 2. Deploy Infrastructure (Terraform)

Provision the entire self-healing infrastructure stack automatically:

```bash
cd terraform
terraform init
terraform apply -auto-approve

```

*Note: Save the `sqs_queue_url` from the output and export it:* `export SQS_QUEUE_URL="<your_sqs_url>"`

### 3. Run Pipeline Scripts

**Ingest Text to S3:**

```bash
python scripts/gutenberg_to_s3.py --book-id 1342

```

**Populate SQS Queue:**

```bash
python scripts/populate_sqs.py

```

**Run Single Unit Test Worker Locally:**

```bash
python scripts/tts_worker-single_instance.py

```

**Analyze Benchmarks:**

```bash
python scripts/analysis.py

```

---

## Core Features & 2026 Standards

* **Infrastructure as Code:** 100% automated provisioning via **Terraform** covering network security boundaries, storage, and IAM profiles.
* **Elastic Scaling:** EC2 Auto Scaling Groups (`c8g.xlarge` ARM64 instances) scale horizontally based on cluster message pressure.
* **Fail-Safe Architecture:** Integrated SQS **Dead Letter Queue (DLQ)** with worker back-off mechanics (`change_message_visibility`) to handle corrupted files or API drops gracefully.
* **Dynamic Telemetry:** Workers query **IMDSv2** to log execution hardware and project precise cost-efficiency matrices to the S3 data lakehouse without hardcoded values.
