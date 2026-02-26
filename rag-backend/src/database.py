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
        try:
            self.client = MongoClient(
                Config.MONGO_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000
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
    
    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self.initialized = False
            print("✓ Closed MongoDB connection")


def get_mongo_client():
    """Get singleton MongoDB client instance."""
    return MongoDBClient()
