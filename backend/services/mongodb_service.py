"""
MongoDB service for ASHA Voice — PyMongo singleton with in-memory fallback for demo.
Supports multi-tenant database routing:
- 'Hasha': primary/existing database used by prakajayavel1994@gmail.com and demo accounts
- 'Hasha_<worker_id>': fresh isolated database for newly registered accounts
- 'users' collection is always centrally stored in the primary database
"""
import os
import uuid
import logging
import contextvars
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# Context variable to hold the current request's tenant database name
_current_db_name: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_db_name", default=None
)


def set_current_db_name(name: Optional[str]):
    _current_db_name.set(name)


def get_current_db_name() -> Optional[str]:
    return _current_db_name.get()


try:
    from pymongo import MongoClient, ASCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    logger.warning("pymongo not installed; in-memory fallback only")


class MongoDBService:
    """Singleton MongoDB service with multi-tenant dynamic database routing and in-memory fallback."""

    _instance = None
    _client = None
    _db = None
    _primary_db_name = "Hasha"
    _memory_store: Optional[Dict[str, List]] = None
    _custom_memory_stores: Optional[Dict[str, Dict[str, List]]] = None
    _initialized_dbs: set = set()
    _connected: bool = False

    COLLECTIONS = [
        'users', 'beneficiaries', 'visits',
        'followups', 'danger_alerts', 'voice_sessions', 'audit_logs'
    ]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized_dbs = set()
            cls._instance._custom_memory_stores = {}
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
            self._client = MongoClient(
                uri,
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=30000,
                socketTimeoutMS=30000
            )
            logger.info("Testing connection with ping...")
            self._client.admin.command('ping')
            db_name = os.environ.get('MONGODB_DB_NAME', '') or self._client.get_default_database().name or 'Hasha'
            self._primary_db_name = db_name
            self._db = self._client[db_name]
            logger.info(f"Creating indexes for primary database: {db_name}")
            self._create_indexes(self._db)
            self._initialized_dbs.add(db_name)
            self._connected = True
            logger.info(f"[SUCCESS] MongoDB Atlas connected successfully to database: {db_name}")
            return True
        except ServerSelectionTimeoutError as e:
            logger.error(f"MongoDB connection failed: ServerSelectionTimeoutError - Cannot reach server")
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
        self._custom_memory_stores = {}
        self._db = None
        self._connected = False
        logger.info("Using in-memory store (demo mode)")

    def _create_indexes(self, target_db=None):
        db = target_db if target_db is not None else self._db
        if db is None:
            return
        try:
            db.beneficiaries.create_index([("beneficiary_id", ASCENDING)], unique=True)
            db.beneficiaries.create_index([("name", ASCENDING)])
            db.visits.create_index([("beneficiary_id", ASCENDING)])
            db.visits.create_index([("visit_date", ASCENDING)])
            db.visits.create_index([("confirmation_status", ASCENDING)])
            db.followups.create_index([("beneficiary_id", ASCENDING)])
            db.followups.create_index([("due_date", ASCENDING)])
            db.followups.create_index([("status", ASCENDING)])
            db.danger_alerts.create_index([("beneficiary_id", ASCENDING)])
            db.danger_alerts.create_index([("created_at", ASCENDING)])
        except Exception as e:
            logger.error(f"Index creation failed: {type(e).__name__}")

    # ------------------------------------------------------------------ dynamic DB resolution

    def _get_db(self, collection: str = None):
        """
        Returns the appropriate database for this request/collection.
        The 'users' collection is always kept in the primary central database ('Hasha').
        Clinical and tracking data (beneficiaries, visits, alerts) route to the tenant's database.
        """
        self.ensure_connected()
        if self._db is None or self._client is None:
            return None
        # 'users' is central authentication store
        if collection == 'users':
            return self._db

        custom_name = _current_db_name.get()
        if custom_name and custom_name != self._primary_db_name:
            target_db = self._client[custom_name]
            if custom_name not in self._initialized_dbs:
                self._create_indexes(target_db)
                self._initialized_dbs.add(custom_name)
            return target_db

        return self._db

    def _get_memory_store(self, collection: str = None) -> dict:
        """In-memory store routing for tests/demo fallback."""
        self._ensure_memory()
        if collection == 'users':
            return self._memory_store

        custom_name = _current_db_name.get()
        if custom_name and custom_name != self._primary_db_name:
            if self._custom_memory_stores is None:
                self._custom_memory_stores = {}
            if custom_name not in self._custom_memory_stores:
                self._custom_memory_stores[custom_name] = {col: [] for col in self.COLLECTIONS}
            return self._custom_memory_stores[custom_name]

        return self._memory_store

    # ------------------------------------------------------------------ status

    def is_connected(self) -> bool:
        return self._connected

    def status(self) -> dict:
        self.ensure_connected()
        active_db = _current_db_name.get() or self._primary_db_name
        return {
            "connected": self._connected,
            "mode": "mongodb_atlas" if self._connected else "in_memory",
            "active_database": active_db,
            "collections": self.COLLECTIONS,
        }

    # ------------------------------------------------------------------ helpers

    def ensure_connected(self):
        """Lazily connect on first use if not already connected."""
        if not self._connected and self._memory_store is None:
            self.connect()

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
        db = self._get_db(collection)
        if db is not None:
            db[collection].insert_one(doc)
            doc.pop('_id', None)
        else:
            mem = self._get_memory_store(collection)
            mem[collection].append(doc)
        return doc

    def find_all(self, collection: str, query: dict = None, limit: int = 100) -> List[dict]:
        self.ensure_connected()
        query = query or {}
        db = self._get_db(collection)
        if db is not None:
            cursor = db[collection].find(query, {'_id': 0}).limit(limit)
            return list(cursor)
        mem = self._get_memory_store(collection)
        items = mem.get(collection, [])
        if query:
            items = [i for i in items if self._matches(i, query)]
        return items[:limit]

    def find_one(self, collection: str, query: dict) -> Optional[dict]:
        self.ensure_connected()
        db = self._get_db(collection)
        if db is not None:
            doc = db[collection].find_one(query, {'_id': 0})
            return doc
        mem = self._get_memory_store(collection)
        for item in mem.get(collection, []):
            if self._matches(item, query):
                return item
        return None

    def update_one(self, collection: str, query: dict, update: dict) -> bool:
        self.ensure_connected()
        update_data = update.get('$set', update)
        update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
        db = self._get_db(collection)
        if db is not None:
            result = db[collection].update_one(query, {'$set': update_data})
            return result.modified_count > 0
        mem = self._get_memory_store(collection)
        for item in mem.get(collection, []):
            if self._matches(item, query):
                item.update(update_data)
                return True
        return False

    def update_many(self, collection: str, query: dict, update: dict) -> int:
        self.ensure_connected()
        update_data = update.get('$set', update)
        update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
        db = self._get_db(collection)
        if db is not None:
            result = db[collection].update_many(query, {'$set': update_data})
            return result.modified_count
        mem = self._get_memory_store(collection)
        count = 0
        for item in mem.get(collection, []):
            if self._matches(item, query):
                item.update(update_data)
                count += 1
        return count

    def delete_one(self, collection: str, query: dict) -> bool:
        self.ensure_connected()
        db = self._get_db(collection)
        if db is not None:
            result = db[collection].delete_one(query)
            return result.deleted_count > 0
        mem = self._get_memory_store(collection)
        store = mem.get(collection, [])
        for i, item in enumerate(store):
            if self._matches(item, query):
                store.pop(i)
                return True
        return False

    def count(self, collection: str, query: dict = None) -> int:
        self.ensure_connected()
        query = query or {}
        db = self._get_db(collection)
        if db is not None:
            return db[collection].count_documents(query)
        mem = self._get_memory_store(collection)
        items = mem.get(collection, [])
        if query:
            items = [i for i in items if self._matches(i, query)]
        return len(items)

    def _ensure_memory(self):
        if self._memory_store is None:
            self._memory_store = {col: [] for col in self.COLLECTIONS}
        if self._custom_memory_stores is None:
            self._custom_memory_stores = {}

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
                    flags = re.IGNORECASE if v.get("$options") == "i" else 0
                    if not (isinstance(item_val, str) and re.search(pattern, item_val, flags)):
                        return False
            elif item_val != v:
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


# Singleton instance exported for application-wide use
mongodb_service = MongoDBService()
