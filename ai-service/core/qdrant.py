"""
Qdrant Client Manager
Quản lý kết nối đến Qdrant vector database
"""
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from core.config import settings


class QdrantManager:
    """Qdrant Client Manager"""
    
    def __init__(self):
        """Initialize Qdrant client"""
        self.client = None
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        
    def connect(self):
        """Connect to Qdrant"""
        try:
            self.client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                api_key=settings.QDRANT_API_KEY,
                timeout=30,
                https=False,  # Local Qdrant không dùng HTTPS
                prefer_grpc=False  # Dùng HTTP REST API thay vì gRPC
            )
            
            # Create collection if not exists
            self._ensure_collection()
            
            print(f"✅ Connected to Qdrant at {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
            
        except Exception as e:
            print(f"❌ Qdrant connection error: {e}")
            raise
    
    def _ensure_collection(self):
        """Ensure collection exists"""
        try:
            collections = self.client.get_collections().collections
            collection_names = [col.name for col in collections]
            
            if self.collection_name not in collection_names:
                print(f"Creating Qdrant collection: {self.collection_name}")
                
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=settings.VECTOR_DIMENSION,
                        distance=Distance.COSINE
                    )
                )
                
                print(f"✅ Collection {self.collection_name} created successfully")
            else:
                print(f"✅ Collection {self.collection_name} already exists")
                
        except Exception as e:
            print(f"❌ Collection setup error: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from Qdrant"""
        if self.client:
            self.client.close()
            print("Qdrant connection closed")


# Global instance
qdrant_manager = QdrantManager()
