"""MongoDB connection and collection management."""

from datetime import datetime, timezone
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure
from src.config import Config

class MongoDBClient:
    """MongoDB client for managing connections and collections."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.client = None
            self.db = None
            self.initialized = False
    
    def connect(self):
        """Connect to MongoDB and initialize collections."""
        if self.initialized:
            return
        try:
            self.client = MongoClient(
                Config.MONGO_URI,
                serverSelectionTimeoutMS=30000,  # 30 seconds
                connectTimeoutMS=30000,
                socketTimeoutMS=30000,
                retryWrites=True,
                w='majority'
            )
            # Verify connection
            self.client.admin.command('ping')
            self.db = self.client[Config.MONGO_DB]
            self._initialize_collections()
            self.initialized = True
            print(f"✓ Connected to MongoDB: {Config.MONGO_DB}")
        except (ServerSelectionTimeoutError, ConnectionFailure) as e:
            print(f"✗ Failed to connect to MongoDB: {e}")
            raise
    
    def _initialize_collections(self):
        """Create collections if they don't exist."""
        # Papers collection
        if Config.MONGO_PAPERS_COLLECTION not in self.db.list_collection_names():
            self.db.create_collection(Config.MONGO_PAPERS_COLLECTION)
            self.db[Config.MONGO_PAPERS_COLLECTION].create_index("paper_id", unique=True)
            print(f"✓ Created collection: {Config.MONGO_PAPERS_COLLECTION}")
        
        # Chunks collection
        if Config.MONGO_CHUNKS_COLLECTION not in self.db.list_collection_names():
            self.db.create_collection(Config.MONGO_CHUNKS_COLLECTION)
            self.db[Config.MONGO_CHUNKS_COLLECTION].create_index("chunk_id", unique=True)
            self.db[Config.MONGO_CHUNKS_COLLECTION].create_index("paper_id")
            print(f"✓ Created collection: {Config.MONGO_CHUNKS_COLLECTION}")
        
        # Execution traces collection (Stage 5)
        if "execution_traces" not in self.db.list_collection_names():
            self.db.create_collection("execution_traces")
            self.db["execution_traces"].create_index("execution_id", unique=True)
            self.db["execution_traces"].create_index("timestamp")
            self.db["execution_traces"].create_index("status")
            print(f"✓ Created collection: execution_traces")

        # Workspace projects
        if "projects" not in self.db.list_collection_names():
            self.db.create_collection("projects")
            print("✓ Created collection: projects")
        self.db["projects"].create_index("project_id", unique=True)
        self.db["projects"].create_index([("user_id", 1), ("updated_at", -1)])

        # Stored queries metadata
        if "queries" not in self.db.list_collection_names():
            self.db.create_collection("queries")
            print("✓ Created collection: queries")
        self.db["queries"].create_index("query_id", unique=True)
        self.db["queries"].create_index([("project_id", 1), ("created_at", -1)])
        self.db["queries"].create_index("execution_id")

        # Full persisted query results
        if "query_results" not in self.db.list_collection_names():
            self.db.create_collection("query_results")
            print("✓ Created collection: query_results")
        self.db["query_results"].create_index("query_id", unique=True)
        self.db["query_results"].create_index("execution_id", unique=True)
        self.db["query_results"].create_index([("project_id", 1), ("created_at", -1)])
    
    def get_papers_collection(self):
        """Get papers collection."""
        if not self.initialized:
            self.connect()
        return self.db[Config.MONGO_PAPERS_COLLECTION]
    
    def get_chunks_collection(self):
        """Get chunks collection."""
        if not self.initialized:
            self.connect()
        return self.db[Config.MONGO_CHUNKS_COLLECTION]
    
    def get_traces_collection(self):
        """Get execution traces collection (Stage 5)."""
        if not self.initialized:
            self.connect()
        return self.db["execution_traces"]

    def get_projects_collection(self):
        """Get projects collection."""
        if not self.initialized:
            self.connect()
        return self.db["projects"]

    def get_queries_collection(self):
        """Get queries collection."""
        if not self.initialized:
            self.connect()
        return self.db["queries"]

    def get_query_results_collection(self):
        """Get query results collection."""
        if not self.initialized:
            self.connect()
        return self.db["query_results"]
    
    def store_trace(self, trace: dict) -> str:
        """Store an execution trace in MongoDB.
        
        Args:
            trace: Full trace dict from ExecutionTracer.finalize()
            
        Returns:
            The execution_id of the stored trace.
        """
        if not self.initialized:
            self.connect()
        collection = self.db["execution_traces"]
        collection.replace_one(
            {"execution_id": trace["execution_id"]},
            trace,
            upsert=True,
        )
        return trace["execution_id"]
    
    def get_trace(self, execution_id: str) -> dict | None:
        """Retrieve an execution trace by execution_id.
        
        Args:
            execution_id: UUID of the execution to retrieve.
            
        Returns:
            Trace dict or None if not found.
        """
        if not self.initialized:
            self.connect()
        collection = self.db["execution_traces"]
        result = collection.find_one(
            {"execution_id": execution_id},
            {"_id": 0},  # exclude MongoDB _id
        )
        return result

    def ensure_default_project(self, user_id: str = "local_user") -> dict:
        """Ensure the user has at least one project and return it."""
        projects = self.get_projects_collection()
        existing = projects.find_one(
            {"user_id": user_id, "is_archived": {"$ne": True}},
            {"_id": 0},
            sort=[("updated_at", -1)],
        )
        if existing:
            return existing

        now = datetime.now(timezone.utc).isoformat()
        project = {
            "project_id": f"proj_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}",
            "user_id": user_id,
            "name": "Project 1",
            "description": "",
            "is_archived": False,
            "created_at": now,
            "updated_at": now,
        }
        projects.insert_one(project)
        return project

    def store_query_run(self, query_doc: dict, result_doc: dict) -> None:
        """Persist query metadata and the full result payload."""
        queries = self.get_queries_collection()
        results = self.get_query_results_collection()

        queries.replace_one({"query_id": query_doc["query_id"]}, query_doc, upsert=True)
        results.replace_one({"query_id": result_doc["query_id"]}, result_doc, upsert=True)

    def list_projects(self, user_id: str = "local_user", include_archived: bool = False) -> list[dict]:
        """List user projects ordered by recency."""
        projects = self.get_projects_collection()
        query = {"user_id": user_id}
        if not include_archived:
            query["is_archived"] = {"$ne": True}
        return list(
            projects.find(query, {"_id": 0}).sort("updated_at", -1)
        )

    def update_project(
        self,
        project_id: str,
        user_id: str = "local_user",
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> dict | None:
        """Update mutable project fields and return the updated project document."""
        projects = self.get_projects_collection()
        update_doc: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if name is not None:
            update_doc["name"] = name
        if description is not None:
            update_doc["description"] = description

        result = projects.find_one_and_update(
            {"project_id": project_id, "user_id": user_id, "is_archived": {"$ne": True}},
            {"$set": update_doc},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )
        return result

    def archive_project(self, project_id: str, user_id: str = "local_user") -> bool:
        """Soft-delete a project by marking it archived."""
        projects = self.get_projects_collection()
        result = projects.update_one(
            {"project_id": project_id, "user_id": user_id, "is_archived": {"$ne": True}},
            {
                "$set": {
                    "is_archived": True,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
        return result.modified_count > 0

    def restore_project(self, project_id: str, user_id: str = "local_user") -> bool:
        """Restore an archived project back to active state."""
        projects = self.get_projects_collection()
        result = projects.update_one(
            {"project_id": project_id, "user_id": user_id, "is_archived": True},
            {
                "$set": {
                    "is_archived": False,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
        return result.modified_count > 0

    def hard_delete_project(self, project_id: str, user_id: str = "local_user") -> dict | None:
        """Permanently delete a project and all associated persisted records.

        Returns:
            dict with deletion counters, or None if project was not found for user.
        """
        projects = self.get_projects_collection()
        queries = self.get_queries_collection()
        results = self.get_query_results_collection()
        traces = self.get_traces_collection()

        existing = projects.find_one({"project_id": project_id, "user_id": user_id}, {"_id": 0, "project_id": 1})
        if not existing:
            return None

        query_docs = list(
            queries.find(
                {"project_id": project_id, "user_id": user_id},
                {"_id": 0, "query_id": 1, "execution_id": 1},
            )
        )
        query_ids = [doc.get("query_id") for doc in query_docs if doc.get("query_id")]
        execution_ids = [doc.get("execution_id") for doc in query_docs if doc.get("execution_id")]

        result_delete = results.delete_many({"project_id": project_id, "user_id": user_id})
        query_delete = queries.delete_many({"project_id": project_id, "user_id": user_id})

        # Backward-compatibility cleanup for old rows that may not include project/user fields.
        legacy_result_delete = None
        if query_ids:
            legacy_result_delete = results.delete_many({"query_id": {"$in": query_ids}})

        trace_delete = None
        if execution_ids:
            trace_delete = traces.delete_many({"execution_id": {"$in": execution_ids}})

        project_delete = projects.delete_one({"project_id": project_id, "user_id": user_id})

        return {
            "project_deleted": project_delete.deleted_count,
            "queries_deleted": query_delete.deleted_count,
            "query_results_deleted": result_delete.deleted_count + (legacy_result_delete.deleted_count if legacy_result_delete else 0),
            "traces_deleted": trace_delete.deleted_count if trace_delete else 0,
        }

    def list_project_queries(self, project_id: str) -> list[dict]:
        """List queries under a project ordered by latest first."""
        queries = self.get_queries_collection()
        return list(
            queries.find({"project_id": project_id}, {"_id": 0}).sort("created_at", -1)
        )

    def get_query_result(self, query_id: str) -> dict | None:
        """Retrieve full persisted result payload by query_id."""
        results = self.get_query_results_collection()
        return results.find_one({"query_id": query_id}, {"_id": 0})

    def get_query_result_by_execution(self, execution_id: str) -> dict | None:
        """Retrieve full persisted result payload by execution_id."""
        results = self.get_query_results_collection()
        return results.find_one({"execution_id": execution_id}, {"_id": 0})
    
    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self.initialized = False
            print("✓ Closed MongoDB connection")


def get_mongo_client():
    """Get singleton MongoDB client instance."""
    return MongoDBClient()
