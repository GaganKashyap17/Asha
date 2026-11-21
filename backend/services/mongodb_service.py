"""
MongoDB service for ASHA Voice — PyMongo singleton with in-memory fallback for demo.
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

try:
    from pymongo import MongoClient, ASCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    logger.warning("pymongo not installed; in-memory fallback only")


class MongoDBService:
    """Singleton MongoDB service with in-memory fallback."""

    _instance = None
    _client = None
    _db = None
    _memory_store: Optional[Dict[str, List]] = None
    _connected: bool = False

    COLLECTIONS = [
        'users', 'beneficiaries', 'visits',
        'followups', 'danger_alerts', 'voice_sessions', 'audit_logs'
    ]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ------------------------------------------------------------------ connect

    def connect(self) -> bool:
        uri = os.environ.get('MONGODB_URI', '')
        if not uri or 'username:password' in uri:
            logger.warning("MongoDB URI not configured. Using in-memory fallback for demo.")
            self._use_memory_fallback()
            return False
        if not PYMONGO_AVAILABLE:
            logger.error("pymongo not installed. Using in-memory fallback.")
            self._use_memory_fallback()
            return False
        try:
            logger.info("Attempting MongoDB connection...")
            # Increased timeout to 30 seconds for initial connection
            self._client = MongoClient(
                uri,
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=30000,
                socketTimeoutMS=30000
            )
            logger.info("Testing connection with ping...")
            self._client.admin.command('ping')
            # Explicitly use configured DB name; fall back to URI default
            db_name = os.environ.get('MONGODB_DB_NAME', '') or self._client.get_default_database().name
            self._db = self._client[db_name]
            logger.info(f"Creating indexes for database: {db_name}")
            self._create_indexes()
            self._connected = True
            logger.info(f"✓ MongoDB Atlas connected successfully to database: {db_name}")
            return True
        except ServerSelectionTimeoutError as e:
            logger.error(f"MongoDB connection failed: ServerSelectionTimeoutError - Cannot reach server")
            logger.error(f"  Possible causes: Network issue, IP not whitelisted, firewall blocking")
            logger.error(f"  Details: {str(e)[:200]}")
            self._use_memory_fallback()
            return False
        except ConnectionFailure as e:
            logger.error(f"MongoDB connection failed: ConnectionFailure - {str(e)[:200]}")
            self._use_memory_fallback()
            return False
        except Exception as e:
            logger.error(f"MongoDB connection failed: {type(e).__name__} - {str(e)[:200]}")
            self._use_memory_fallback()
            return False

    def _use_memory_fallback(self):
        self._memory_store = {col: [] for col in self.COLLECTIONS}
        self._db = None
        self._connected = False
        logger.info("Using in-memory store (demo mode)")

    def _create_indexes(self):
        if self._db is None:
            return
        try:
            self._db.beneficiaries.create_index([("beneficiary_id", ASCENDING)], unique=True)
            self._db.beneficiaries.create_index([("name", ASCENDING)])
            self._db.visits.create_index([("beneficiary_id", ASCENDING)])
            self._db.visits.create_index([("visit_date", ASCENDING)])
            self._db.visits.create_index([("confirmation_status", ASCENDING)])
            self._db.followups.create_index([("beneficiary_id", ASCENDING)])
            self._db.followups.create_index([("due_date", ASCENDING)])
            self._db.followups.create_index([("status", ASCENDING)])
            self._db.danger_alerts.create_index([("beneficiary_id", ASCENDING)])
            self._db.danger_alerts.create_index([("created_at", ASCENDING)])
        except Exception as e:
            logger.error(f"Index creation failed: {type(e).__name__}")

    # ------------------------------------------------------------------ status

    def is_connected(self) -> bool:
        return self._connected

    def status(self) -> dict:
        self.ensure_connected()
        return {
            "connected": self._connected,
            "mode": "mongodb_atlas" if self._connected else "in_memory",
            "collections": self.COLLECTIONS,
        }

    # ------------------------------------------------------------------ helpers

    def ensure_connected(self):
        """Lazily connect on first use if not already connected."""
        if not self._connected and self._memory_store is None:
            self.connect()

    def _get_collection(self, name: str):
        """Return PyMongo collection or in-memory list."""
        self.ensure_connected()
        if self._db is not None:
            return self._db[name]
        return None  # caller uses _memory_store

    def _new_id(self) -> str:
        return str(uuid.uuid4())

    # ------------------------------------------------------------------ generic CRUD

    def insert(self, collection: str, document: dict) -> dict:
        """Insert a document; adds _id and created_at if missing."""
        self.ensure_connected()
        doc = document.copy()
        if '_id' not in doc:
            doc['_id'] = self._new_id()
        if 'created_at' not in doc:
            doc['created_at'] = datetime.now(timezone.utc).isoformat()
        if self._db is not None:
            self._db[collection].insert_one(doc)
            doc.pop('_id', None)  # remove ObjectId after insert
        else:
            self._ensure_memory()
            self._memory_store[collection].append(doc)
        return doc

    def find_all(self, collection: str, query: dict = None, limit: int = 100) -> List[dict]:
        self.ensure_connected()
        query = query or {}
        if self._db is not None:
            cursor = self._db[collection].find(query, {'_id': 0}).limit(limit)
            return list(cursor)
        self._ensure_memory()
        items = self._memory_store.get(collection, [])
        if query:
            items = [i for i in items if self._matches(i, query)]
        return items[:limit]

    def find_one(self, collection: str, query: dict) -> Optional[dict]:
        self.ensure_connected()
        if self._db is not None:
            doc = self._db[collection].find_one(query, {'_id': 0})
            return doc
        self._ensure_memory()
        for item in self._memory_store.get(collection, []):
            if self._matches(item, query):
                return item
        return None

    def update_one(self, collection: str, query: dict, update: dict) -> bool:
        self.ensure_connected()
        update_data = update.get('$set', update)
        update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
        if self._db is not None:
            result = self._db[collection].update_one(query, {'$set': update_data})
            return result.modified_count > 0
        self._ensure_memory()
        for item in self._memory_store.get(collection, []):
            if self._matches(item, query):
                item.update(update_data)
                return True
        return False

    def update_many(self, collection: str, query: dict, update: dict) -> int:
        self.ensure_connected()
        update_data = update.get('$set', update)
        update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
        if self._db is not None:
            result = self._db[collection].update_many(query, {'$set': update_data})
            return result.modified_count
        self._ensure_memory()
        count = 0
        for item in self._memory_store.get(collection, []):
            if self._matches(item, query):
                item.update(update_data)
                count += 1
        return count

    def delete_one(self, collection: str, query: dict) -> bool:
        self.ensure_connected()
        if self._db is not None:
            result = self._db[collection].delete_one(query)
            return result.deleted_count > 0
        self._ensure_memory()
        store = self._memory_store.get(collection, [])
        for i, item in enumerate(store):
            if self._matches(item, query):
                store.pop(i)
                return True
        return False

    def count(self, collection: str, query: dict = None) -> int:
        self.ensure_connected()
        query = query or {}
        if self._db is not None:
            return self._db[collection].count_documents(query)
        self._ensure_memory()
        items = self._memory_store.get(collection, [])
        if query:
            items = [i for i in items if self._matches(i, query)]
        return len(items)

    def _ensure_memory(self):
        if self._memory_store is None:
            self._memory_store = {col: [] for col in self.COLLECTIONS}

    @classmethod
    def _matches(cls, item: dict, query: dict) -> bool:
        import re
        if "$or" in query:
            or_clauses = query["$or"]
            if not any(cls._matches(item, clause) for clause in or_clauses):
                return False

        for k, v in query.items():
            if k == "$or":
                continue
            item_val = item.get(k)
            if isinstance(v, dict):
                if "$ne" in v and item_val == v["$ne"]:
                    return False
                if "$in" in v and item_val not in v["$in"]:
                    return False
                if "$nin" in v and item_val in v["$nin"]:
                    return False
                if "$exists" in v:
                    exists = k in item
                    if exists != v["$exists"]:
                        return False
                if "$regex" in v:
                    pattern = v["$regex"]
                    flags = re.IGNORECASE if "i" in v.get("$options", "") else 0
                    if not (isinstance(item_val, str) and re.search(pattern, item_val, flags)):
                        return False
            else:
                if item_val != v:
                    return False
        return True

    # ------------------------------------------------------------------ domain helpers

    def get_user_by_worker_id(self, worker_id: str) -> Optional[dict]:
        return self.find_one('users', {'worker_id': worker_id})

    def get_beneficiary(self, beneficiary_id: str) -> Optional[dict]:
        return self.find_one('beneficiaries', {'beneficiary_id': beneficiary_id, 'is_deleted': {'$ne': True}})

    def get_visits_for_beneficiary(self, beneficiary_id: str) -> List[dict]:
        return self.find_all('visits', {'beneficiary_id': beneficiary_id})

    def get_pending_followups(self) -> List[dict]:
        return self.find_all('followups', {'status': 'pending'})

    def get_active_danger_alerts(self) -> List[dict]:
        return self.find_all('danger_alerts', {'resolved': False})

    def aggregate_dashboard_stats(self) -> dict:
        return {
            "total_beneficiaries": self.count('beneficiaries', {'is_deleted': {'$ne': True}}),
            "total_visits": self.count('visits'),
            "pending_followups": self.count('followups', {'status': 'pending'}),
            "active_danger_alerts": self.count('danger_alerts', {'resolved': False}),
            "confirmed_visits": self.count('visits', {'confirmation_status': 'confirmed'}),
            "pending_visits": self.count('visits', {'confirmation_status': 'pending'}),
        }


# Singleton instance
mongodb_service = MongoDBService()
