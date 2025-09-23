"""Utility to ensure MinIO buckets exist."""

import os
import sys

import boto3
from botocore.exceptions import ClientError

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_USER")
MINIO_SECRET_KEY = os.environ.get("MINIO_PASS")
DEFAULT_BUCKETS = os.environ.get("MINIO_BUCKETS", "bronze,silver,gold").split(",")

if not MINIO_ACCESS_KEY or not MINIO_SECRET_KEY:
    sys.stderr.write("Missing MINIO_USER or MINIO_PASS environment variables\n")
    sys.exit(1)

client = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    region_name="us-east-1",
)

created = 0
for bucket in DEFAULT_BUCKETS:
    bucket = bucket.strip()
    if not bucket:
        continue
    try:
        client.create_bucket(Bucket=bucket)
        print(f"[info] Created bucket {bucket}")
        created += 1
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            print(f"[info] Bucket {bucket} already present")
        else:
            raise

print(f"[done] Buckets ready (new={created})")
