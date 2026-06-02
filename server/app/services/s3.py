# S3-совместимое хранилище (MinIO)
import uuid
import boto3
from botocore.config import Config as BotoConfig
from fastapi import UploadFile, HTTPException
from app.config import settings

ALLOWED_EXTENSIONS = {
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg',
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'txt', 'csv', 'md', 'json', 'xml',
    'zip', 'rar', '7z', 'tar', 'gz',
    'mp3', 'mp4', 'wav', 'ogg', 'webm',
}


_s3_client = None
_bucket_verified = False


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=BotoConfig(
                signature_version="s3v4",
                connect_timeout=3,
                read_timeout=3,
                retries={"max_attempts": 0, "mode": "standard"},
            ),
        )
    return _s3_client


def ensure_bucket():
    global _bucket_verified
    if _bucket_verified:
        return
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=settings.S3_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=settings.S3_BUCKET)
    # Ensure public-read policy so nginx can proxy files to the browser
    import json as _json
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{settings.S3_BUCKET}/*"]
        }]
    }
    try:
        s3.put_bucket_policy(Bucket=settings.S3_BUCKET, Policy=_json.dumps(policy))
    except Exception:
        pass
    _bucket_verified = True


async def upload_file_to_s3(file: UploadFile, prefix: str = "uploads") -> str:
    """Загрузка файла в S3, возвращает URL"""
    s3 = get_s3_client()
    ensure_bucket()

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "bin"
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Недопустимый тип файла: .{ext}")

    key = f"{prefix}/{uuid.uuid4().hex}.{ext}"

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Файл слишком большой")

    s3.put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=content,
        ContentType=file.content_type or "application/octet-stream",
    )
    return f"/files/{key}"


def delete_file_from_s3(file_url: str) -> bool:
    """Delete a file from S3 by its URL (e.g. /files/chat/xxx/yyy.ext). Returns True if deleted."""
    if not file_url:
        return False
    prefix = "/files/"
    if file_url.startswith(prefix):
        key = file_url[len(prefix):]
    else:
        return False
    s3 = get_s3_client()
    ensure_bucket()
    try:
        s3.delete_object(Bucket=settings.S3_BUCKET, Key=key)
        return True
    except Exception:
        return False
