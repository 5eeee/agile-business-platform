import boto3
from app.config import settings

s3 = boto3.client("s3",
    endpoint_url=settings.S3_ENDPOINT,
    aws_access_key_id=settings.S3_ACCESS_KEY,
    aws_secret_access_key=settings.S3_SECRET_KEY
)

resp = s3.list_objects_v2(Bucket=settings.S3_BUCKET, Prefix="music/", MaxKeys=5)
contents = resp.get("Contents", [])
print("Found", len(contents), "objects")
for obj in contents:
    print(" ", obj["Key"], "-", obj["Size"], "bytes")
