"""
Backup service: MongoDB dump + Cloudflare R2 storage.
R2 is optional — if credentials are not set, backups are stored locally only.
"""
import os
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

BACKUP_DIR = Path("/app/backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _get_r2_client():
    """Return a boto3 S3 client pointed at Cloudflare R2, or None if not configured."""
    account_id = os.environ.get("R2_ACCOUNT_ID", "").strip()
    access_key = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    endpoint = os.environ.get("R2_ENDPOINT_URL", "").strip()

    if not all([account_id, access_key, secret_key, endpoint]):
        return None

    try:
        import boto3
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )
    except Exception as exc:
        logger.warning("Could not create R2 client: %s", exc)
        return None


async def create_backup(db_name: str) -> dict:
    """
    Run mongodump → compressed archive → upload to R2 (if configured).
    Returns metadata dict.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{db_name}_{timestamp}.archive.gz"
    local_path = BACKUP_DIR / filename

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")

    cmd = [
        "mongodump",
        f"--uri={mongo_url}",
        f"--db={db_name}",
        f"--archive={local_path}",
        "--gzip",
    ]

    logger.info("Starting backup: %s", filename)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        err = stderr.decode().strip()
        logger.error("mongodump failed: %s", err)
        return {"success": False, "error": err}

    size_bytes = local_path.stat().st_size
    size_mb = round(size_bytes / 1_048_576, 2)
    logger.info("Backup created: %s (%.2f MB)", filename, size_mb)

    result = {
        "success": True,
        "filename": filename,
        "local_path": str(local_path),
        "size_mb": size_mb,
        "timestamp": timestamp,
        "r2_uploaded": False,
    }

    # Upload to R2 if configured
    r2 = _get_r2_client()
    bucket = os.environ.get("R2_BUCKET_NAME", "agripos-backups")
    if r2:
        try:
            key = f"backups/{db_name}/{filename}"
            r2.upload_file(str(local_path), bucket, key)
            result["r2_uploaded"] = True
            result["r2_key"] = key
            logger.info("Uploaded to R2: %s", key)
        except Exception as exc:
            logger.warning("R2 upload failed (backup saved locally): %s", exc)

    return result


async def list_backups(db_name: str) -> list:
    """List backups — from R2 if configured, else from local disk."""
    r2 = _get_r2_client()
    bucket = os.environ.get("R2_BUCKET_NAME", "agripos-backups")

    if r2:
        try:
            prefix = f"backups/{db_name}/"
            resp = r2.list_objects_v2(Bucket=bucket, Prefix=prefix)
            items = []
            for obj in resp.get("Contents", []):
                if obj["Key"].endswith("/"):
                    continue
                items.append({
                    "filename": obj["Key"].split("/")[-1],
                    "key": obj["Key"],
                    "size_mb": round(obj["Size"] / 1_048_576, 2),
                    "created_at": obj["LastModified"].isoformat(),
                    "source": "r2",
                })
            return sorted(items, key=lambda x: x["created_at"], reverse=True)
        except Exception as exc:
            logger.warning("R2 list failed, falling back to local: %s", exc)

    # Local fallback
    files = sorted(BACKUP_DIR.glob(f"{db_name}_*.archive.gz"), reverse=True)
    return [
        {
            "filename": f.name,
            "key": None,
            "size_mb": round(f.stat().st_size / 1_048_576, 2),
            "created_at": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            "source": "local",
        }
        for f in files
    ]


async def restore_backup(db_name: str, filename: str) -> dict:
    """Download from R2 (if needed) then run mongorestore."""
    local_path = BACKUP_DIR / filename

    # Download from R2 if not already local
    if not local_path.exists():
        r2 = _get_r2_client()
        bucket = os.environ.get("R2_BUCKET_NAME", "agripos-backups")
        if not r2:
            return {"success": False, "error": "File not found locally and R2 not configured"}
        key = f"backups/{db_name}/{filename}"
        try:
            r2.download_file(bucket, key, str(local_path))
        except Exception as exc:
            return {"success": False, "error": f"R2 download failed: {exc}"}

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    cmd = [
        "mongorestore",
        f"--uri={mongo_url}",
        f"--db={db_name}",
        f"--archive={local_path}",
        "--gzip",
        "--drop",
    ]

    logger.info("Restoring from: %s", filename)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        err = stderr.decode().strip()
        logger.error("mongorestore failed: %s", err)
        return {"success": False, "error": err}

    logger.info("Restore complete: %s", filename)
    return {"success": True, "filename": filename}


def delete_old_local_backups(db_name: str, retain_days: int = 30):
    """Remove local backup files older than retain_days."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=retain_days)
    for f in BACKUP_DIR.glob(f"{db_name}_*.archive.gz"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            f.unlink()
            logger.info("Deleted old local backup: %s", f.name)
