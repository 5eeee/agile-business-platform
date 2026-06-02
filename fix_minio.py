import boto3, json
from app.config import settings

s3 = boto3.client("s3",
    endpoint_url=settings.S3_ENDPOINT,
    aws_access_key_id=settings.S3_ACCESS_KEY,
    aws_secret_access_key=settings.S3_SECRET_KEY
)

# Set public read policy on bucket
policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"AWS": ["*"]},
        "Action": ["s3:GetObject"],
        "Resource": ["arn:aws:s3:::%s/*" % settings.S3_BUCKET]
    }]
}
s3.put_bucket_policy(Bucket=settings.S3_BUCKET, Policy=json.dumps(policy))
print("Bucket policy set to public-read for", settings.S3_BUCKET)

# Count total music files
resp = s3.list_objects_v2(Bucket=settings.S3_BUCKET, Prefix="music/")
count = resp.get("KeyCount", 0)
print("Total music files:", count)
