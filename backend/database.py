"""
Database connection and shared utilities for AgriPOS
"""
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
import os
import uuid
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ.get('JWT_SECRET', 'agripos_default_secret')

def now_iso():
    """Return current UTC time as ISO string"""
    return datetime.now(timezone.utc).isoformat()

def new_id():
    """Generate a new UUID string"""
    return str(uuid.uuid4())
