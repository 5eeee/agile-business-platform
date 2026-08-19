# S3-совместимое хранилище (MinIO)
import base64
import hashlib
import os
import uuid
from urllib.parse import unquote
import boto3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
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
_ENCRYPTED_PREFIXES = ("documents/", "tasks/", "chat/")
_ENCRYPTION_MAGIC = b"AGILE-AES-GCM-1\x00"


def _encryption_key() -> bytes:
    """Вернуть 32-байтовый ключ, не сохраняя его рядом с файлами."""
    configured = settings.FILE_ENCRYPTION_KEY.strip()
    if configured:
        try:
            decoded = base64.urlsafe_b64decode(configured + "=" * (-len(configured) % 4))
        except Exception as exc:
            raise RuntimeError("FILE_ENCRYPTION_KEY должен быть base64url") from exc
        if len(decoded) != 32:
            raise RuntimeError("FILE_ENCRYPTION_KEY должен содержать ровно 32 байта")
        return decoded
    return hashlib.sha256(("agile-file-v1:" + settings.SECRET_KEY).encode("utf-8")).digest()


def _encrypt(content: bytes, key: str) -> bytes:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_encryption_key()).encrypt(nonce, content, key.encode("utf-8"))
    return _ENCRYPTION_MAGIC + nonce + ciphertext


def _decrypt(content: bytes, key: str) -> bytes:
    if not content.startswith(_ENCRYPTION_MAGIC):
        return content  # обратная совместимость со старыми незашифрованными объектами
    offset = len(_ENCRYPTION_MAGIC)
    nonce = content[offset:offset + 12]
    ciphertext = content[offset + 12:]
    return AESGCM(_encryption_key()).decrypt(nonce, ciphertext, key.encode("utf-8"))


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=BotoConfig(signature_version="s3v4"),
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


async def upload_file_to_s3(file: UploadFile, prefix: str = "uploads", encrypt: bool | None = None) -> str:
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

    should_encrypt = prefix.startswith(_ENCRYPTED_PREFIXES) if encrypt is None else encrypt
    payload = _encrypt(content, key) if should_encrypt else content
    metadata = {
        "encrypted": "aes-256-gcm" if should_encrypt else "none",
        "original-content-type": file.content_type or "application/octet-stream",
    }
    s3.put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=payload,
        ContentType="application/octet-stream" if should_encrypt else (file.content_type or "application/octet-stream"),
        Metadata=metadata,
    )
    return f"/api/secure-files/{key}" if should_encrypt else f"/files/{key}"


def download_file_from_s3(file_path: str) -> tuple[bytes, str]:
    """Скачать объект и прозрачно расшифровать новый защищённый формат."""
    raw_path = unquote(file_path or "").lstrip("/")
    if raw_path.startswith("api/secure-files/"):
        raw_path = raw_path[len("api/secure-files/"):]
    elif raw_path.startswith("files/"):
        raw_path = raw_path[len("files/"):]
    if not raw_path or ".." in raw_path.split("/"):
        raise HTTPException(status_code=400, detail="Некорректный путь файла")
    try:
        obj = get_s3_client().get_object(Bucket=settings.S3_BUCKET, Key=raw_path)
        payload = obj["Body"].read()
        metadata = obj.get("Metadata") or {}
        content_type = metadata.get("original-content-type") or obj.get("ContentType") or "application/octet-stream"
        return _decrypt(payload, raw_path), content_type
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Файл не найден или повреждён") from exc


def delete_file_from_s3(file_url: str) -> bool:
    """Delete a file from S3 by its URL (e.g. /files/chat/xxx/yyy.ext). Returns True if deleted."""
    if not file_url:
        return False
    prefixes = ("/files/", "/api/secure-files/")
    key = next((file_url[len(prefix):] for prefix in prefixes if file_url.startswith(prefix)), None)
    if not key:
        return False
    s3 = get_s3_client()
    ensure_bucket()
    try:
        s3.delete_object(Bucket=settings.S3_BUCKET, Key=key)
        return True
    except Exception:
        return False
