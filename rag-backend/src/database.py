"""MongoDB connection and collection management."""

from pymongo import MongoClient
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
    
    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self.initialized = False
            print("✓ Closed MongoDB connection")


def get_mongo_client():
    """Get singleton MongoDB client instance."""
    return MongoDBClient()
