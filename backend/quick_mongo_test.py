import os
from dotenv import load_dotenv
load_dotenv()

try:
    from pymongo import MongoClient
    uri = os.getenv('MONGODB_URI')
    print(f"Connecting to: {uri[:50]}...")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("SUCCESS: Connected to MongoDB!")
    print(f"Database: {os.getenv('MONGODB_DB_NAME')}")
    db = client[os.getenv('MONGODB_DB_NAME')]
    print(f"Collections: {db.list_collection_names()}")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
