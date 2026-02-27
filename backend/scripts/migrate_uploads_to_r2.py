#!/usr/bin/env python3
"""
One-time migration: Move existing local /app/uploads/ files to Cloudflare R2.
Updates upload_sessions in MongoDB to use r2_key instead of stored_path.

Usage (on VPS):
  cd /var/www/agribooks/backend
  source venv/bin/activate
  python3 scripts/migrate_uploads_to_r2.py

Safe to run multiple times — skips files already migrated (have r2_key).
"""
import os
import sys
import asyncio
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file manually (script runs outside FastAPI)
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), value)
    print(f"Loaded .env from {env_path}")

from motor.motor_asyncio import AsyncIOMotorClient
from utils.r2_storage import upload_file, file_exists, build_key


async def migrate():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "agribooks")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    sessions = await db.upload_sessions.find({}, {"_id": 0}).to_list(100000)
    print(f"Found {len(sessions)} upload sessions to check")

    migrated = 0
    skipped = 0
    errors = 0
    already_r2 = 0

    for session in sessions:
        session_id = session.get("id", "")
        org_id = session.get("org_id") or session.get("organization_id") or "default"
        record_type = session.get("record_type", "unknown")
        record_id = session.get("record_id", "unknown")
        files = session.get("files", [])
        updated_files = []
        session_changed = False

        for f in files:
            if f.get("r2_key"):
                already_r2 += 1
                updated_files.append(f)
                continue

            stored_path = f.get("stored_path", "")
            if not stored_path:
                updated_files.append(f)
                continue

            local_file = Path(stored_path)
            if not local_file.exists():
                print(f"  SKIP (missing): {stored_path}")
                skipped += 1
                updated_files.append(f)
                continue

            # Build R2 key and upload
            file_id = f.get("id", local_file.stem)
            ext = local_file.suffix or ".jpg"
            filename = f"{file_id}{ext}"
            content_type = f.get("content_type", "image/jpeg")

            try:
                content = local_file.read_bytes()
                result = await upload_file(org_id, record_type, record_id, filename, content, content_type)
                f["r2_key"] = result["key"]
                session_changed = True
                migrated += 1
                print(f"  OK: {stored_path} → {result['key']} ({len(content)} bytes)")
            except Exception as exc:
                print(f"  ERROR: {stored_path} — {exc}")
                errors += 1

            updated_files.append(f)

        if session_changed:
            await db.upload_sessions.update_one(
                {"id": session_id},
                {"$set": {"files": updated_files, "org_id": org_id}}
            )

    print(f"\n{'='*50}")
    print(f"Migration complete:")
    print(f"  Migrated to R2:  {migrated}")
    print(f"  Already on R2:   {already_r2}")
    print(f"  Skipped (missing): {skipped}")
    print(f"  Errors:          {errors}")
    print(f"\nLocal files are NOT deleted. After verifying, you can remove /app/uploads/ manually.")


if __name__ == "__main__":
    asyncio.run(migrate())
