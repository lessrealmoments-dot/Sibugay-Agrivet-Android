"""
Data Migration: Assign branch_id to customers without one.
Assigns to the default (first) branch.
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from pathlib import Path
from dotenv import load_dotenv

# Load env
load_dotenv(Path(__file__).parent / '.env')

async def migrate_customers():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client[os.environ['DB_NAME']]
    
    # Get default branch
    default_branch = await db.branches.find_one({"active": True}, {"_id": 0})
    if not default_branch:
        print("ERROR: No active branch found!")
        return
    
    default_branch_id = default_branch["id"]
    print(f"Default branch: {default_branch['name']} ({default_branch_id})")
    
    # Find customers without branch_id
    customers_no_branch = await db.customers.count_documents({
        "$or": [
            {"branch_id": {"$exists": False}},
            {"branch_id": ""},
            {"branch_id": None}
        ]
    })
    
    print(f"Customers without branch_id: {customers_no_branch}")
    
    if customers_no_branch > 0:
        result = await db.customers.update_many(
            {
                "$or": [
                    {"branch_id": {"$exists": False}},
                    {"branch_id": ""},
                    {"branch_id": None}
                ]
            },
            {"$set": {"branch_id": default_branch_id}}
        )
        print(f"Updated {result.modified_count} customers with branch_id: {default_branch_id}")
    else:
        print("No customers need migration.")
    
    # Verify
    final_count = await db.customers.count_documents({"branch_id": {"$exists": True, "$ne": ""}})
    total = await db.customers.count_documents({})
    print(f"Final: {final_count}/{total} customers have branch_id")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(migrate_customers())
