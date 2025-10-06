import boto3
import os
from dotenv import load_dotenv
load_dotenv()  # Load .env variables

# Initialize S3 client 
s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("REGION")
)

BUCKET_NAME = os.getenv("AWS_S3_BUCKET")

# Upload File Function
def upload_file(local_file_path: str, s3_key: str):
    try:
        s3.upload_file(
            local_file_path,
            BUCKET_NAME,
            s3_key,
            ExtraArgs={
                'ContentType': 'application/pdf',
                'ContentDisposition': 'inline'
            }
        )
        print(f"✅ Uploaded {local_file_path} to s3://{BUCKET_NAME}/{s3_key}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")

# Download File Function
def download_file(s3_key: str, local_file_path: str):
    try:
        s3.download_file(BUCKET_NAME, s3_key, local_file_path)
        print(f"✅ Downloaded s3://{BUCKET_NAME}/{s3_key} to {local_file_path}")
    except Exception as e:
        print(f"❌ Download failed: {e}")

# List Files in Bucket Function
def list_bucket_files(prefix: str = ""):
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        if "Contents" in response:
            print("📁 Files in bucket:")
            for item in response["Contents"]:
                print(" -", item["Key"])
        else:
            print("📁 No files found.")
    except Exception as e:
        print(f"❌ Listing failed: {e}")