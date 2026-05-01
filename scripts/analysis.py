import boto3
import json
from datetime import datetime, timezone

# CONFIGURATION
BUCKET_NAME = "tts-pipeline-output"
LOGS_PREFIX = "logs/gutenberg/"

# DEFINE THE TIME WINDOWS (UTC)
# Horizontal: April 27, 19:03:25 to April 28, 02:02:20
HORIZONTAL_START = datetime(2026, 4, 27, 19, 3, 25, tzinfo=timezone.utc)
HORIZONTAL_END = datetime(2026, 4, 28, 2, 2, 20, tzinfo=timezone.utc)

# Vertical: April 28, 02:02:20 to April 28, 15:19:50
VERTICAL_START = datetime(2026, 4, 28, 2, 2, 20, tzinfo=timezone.utc)
VERTICAL_END = datetime(2026, 4, 28, 15, 19, 50, tzinfo=timezone.utc)

s3 = boto3.client('s3')

def get_architecture_group(log_time_str):
    """Assigns a log to a group based on its timestamp."""
    # Convert string (e.g. 2026-04-27T19:08:49.010484) to datetime object
    log_dt = datetime.fromisoformat(log_time_str).replace(tzinfo=timezone.utc)

    if HORIZONTAL_START <= log_dt < HORIZONTAL_END:
        return "Horizontal Cluster (4x xlarge)"
    elif VERTICAL_START <= log_dt <= VERTICAL_END:
        return "Vertical Node (1x 4xlarge)"
    return "Unknown/Outside Test Range"

def analyze_logs():
    stats = {
        "Horizontal Cluster (4x xlarge)": {"count": 0, "words": 0, "time": 0, "cost": 0, "rtfs": []},
        "Vertical Node (1x 4xlarge)": {"count": 0, "words": 0, "time": 0, "cost": 0, "rtfs": []}
    }

    print(f"🔍 Fetching logs from s3://{BUCKET_NAME}/{LOGS_PREFIX}...")

    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=LOGS_PREFIX):
        for obj in page.get('Contents', []):
            if not obj['Key'].endswith('.json'): continue

            content = s3.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])['Body'].read()
            data = json.loads(content)

            group = get_architecture_group(data['timestamp'])

            if group in stats:
                stats[group]["count"] += 1
                stats[group]["words"] += data['word_count']
                stats[group]["time"] += data['processing_time_sec']
                stats[group]["cost"] += float(data['cost_usd'])
                stats[group]["rtfs"].append(data['rtf'])

    print("\n" + "="*60)
    print("FINAL ARCHITECTURE COMPARISON REPORT")
    print("="*60)

    for group, data in stats.items():
        if data["count"] == 0: continue

        avg_rtf = sum(data["rtfs"]) / data["count"]
        words_per_sec = data["words"] / data["time"]
        cost_per_100k_words = (data["cost"] / data["words"]) * 100000

        print(f"\n📊 ARCHITECTURE: {group}")
        print(f"   Books Processed:   {data['count']}")
        print(f"   Total Words:       {data['words']:,}")
        print(f"   Avg RTF:           {avg_rtf:.2f}x")
        print(f"   Inference Speed:   {words_per_sec:.2f} words/sec")
        print(f"   Cost Efficiency:   ${cost_per_100k_words:.4f} per 100k words")
        print(f"   Total Phase Cost:  ${data['cost']:.4f}")

if __name__ == "__main__":
    analyze_logs()
