"""
MongoDB Connection Diagnostic Script
Tests connection and provides detailed error information
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 60)
print("MongoDB Connection Diagnostic")
print("=" * 60)

# Check if pymongo is installed
try:
    import pymongo
    print(f"✓ PyMongo installed: version {pymongo.__version__}")
except ImportError as e:
    print(f"✗ PyMongo not installed: {e}")
    sys.exit(1)

# Check if dnspython is installed (required for SRV connection strings)
try:
    import dns
    print(f"✓ dnspython installed: version {dns.__version__}")
except ImportError as e:
    print(f"✗ dnspython not installed (required for mongodb+srv://): {e}")
    sys.exit(1)

# Get connection string
mongodb_uri = os.environ.get('MONGODB_URI', '')
db_name = os.environ.get('MONGODB_DB_NAME', '')

if not mongodb_uri:
    print("✗ MONGODB_URI not set in environment")
    sys.exit(1)

# Mask password for display
display_uri = mongodb_uri
if '@' in mongodb_uri:
    parts = mongodb_uri.split('@')
    creds = parts[0].split('://')[-1]
    if ':' in creds:
        user = creds.split(':')[0]
        display_uri = mongodb_uri.replace(creds, f"{user}:****")

print(f"\nConnection String: {display_uri}")
print(f"Database Name: {db_name}")
print("\n" + "=" * 60)
print("Testing Connection...")
print("=" * 60)

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, OperationFailure
    
    # Test connection with short timeout
    print("\n1. Creating MongoDB client...")
    client = MongoClient(
        mongodb_uri,
        serverSelectionTimeoutMS=10000,  # 10 second timeout
        connectTimeoutMS=10000,
        socketTimeoutMS=10000
    )
    
    print("✓ Client created successfully")
    
    # Test ping
    print("\n2. Testing server ping...")
    client.admin.command('ping')
    print("✓ Server ping successful")
    
    # Test database access
    print("\n3. Testing database access...")
    if db_name:
        db = client[db_name]
    else:
        db = client.get_default_database()
        db_name = db.name
    
    print(f"✓ Database accessed: {db_name}")
    
    # List collections
    print("\n4. Listing collections...")
    collections = db.list_collection_names()
    if collections:
        print(f"✓ Found {len(collections)} collections:")
        for col in collections[:10]:  # Show first 10
            print(f"  - {col}")
    else:
        print("⚠ No collections found (database may be empty)")
    
    # Test a simple query
    print("\n5. Testing query operation...")
    test_collection = db['beneficiaries']
    count = test_collection.count_documents({})
    print(f"✓ Query successful - beneficiaries count: {count}")
    
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED - MongoDB connection is working!")
    print("=" * 60)
    
    client.close()

except ServerSelectionTimeoutError as e:
    print(f"\n✗ ServerSelectionTimeoutError: Cannot reach MongoDB server")
    print(f"   Error: {e}")
    print("\n   Common causes:")
    print("   1. Network connectivity issues")
    print("   2. IP address not whitelisted in MongoDB Atlas")
    print("   3. Firewall blocking outbound connections")
    print("   4. DNS resolution issues")
    print("\n   Solutions:")
    print("   - Check your internet connection")
    print("   - Add 0.0.0.0/0 to IP whitelist in MongoDB Atlas (Network Access)")
    print("   - Check Windows Firewall settings")
    sys.exit(1)

except OperationFailure as e:
    print(f"\n✗ OperationFailure: Authentication or authorization failed")
    print(f"   Error: {e}")
    print("\n   Common causes:")
    print("   1. Invalid username or password")
    print("   2. User doesn't have required permissions")
    print("   3. Database name doesn't match user permissions")
    print("\n   Solutions:")
    print("   - Verify credentials in MongoDB Atlas")
    print("   - Check user permissions for the database")
    sys.exit(1)

except ConnectionFailure as e:
    print(f"\n✗ ConnectionFailure: Cannot establish connection")
    print(f"   Error: {e}")
    sys.exit(1)

except Exception as e:
    print(f"\n✗ Unexpected error: {type(e).__name__}")
    print(f"   Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
