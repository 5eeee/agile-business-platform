import boto3, asyncio
from app.config import settings
from app.database import async_session
from sqlalchemy import text

s3 = boto3.client("s3",
    endpoint_url=settings.S3_ENDPOINT,
    aws_access_key_id=settings.S3_ACCESS_KEY,
    aws_secret_access_key=settings.S3_SECRET_KEY
)

MIN_SIZE = 500 * 1024

# Find small files
resp = s3.list_objects_v2(Bucket=settings.S3_BUCKET, Prefix="music/", MaxKeys=200)
small_keys = []
for obj in resp.get("Contents", []):
    if obj["Size"] < MIN_SIZE:
        small_keys.append(obj["Key"])
        print(f"  Small: {obj['Key']} ({obj['Size']//1024} KB)")

# Find matching DB rows and delete them
async def cleanup():
    async with async_session() as s:
        for key in small_keys:
            file_url = f"/files/{key}"
            r = await s.execute(text("SELECT id, title, artist FROM playlist_tracks WHERE file_url = :url"), {"url": file_url})
            row = r.fetchone()
            if row:
                print(f"  Deleting DB row: {row[1]} by {row[2]}")
                await s.execute(text("DELETE FROM playlist_tracks WHERE id = :id"), {"id": str(row[0])})
            # Delete from S3
            s3.delete_object(Bucket=settings.S3_BUCKET, Key=key)
            print(f"  Deleted S3: {key}")
        await s.commit()

asyncio.run(cleanup())
print("Cleanup done")
