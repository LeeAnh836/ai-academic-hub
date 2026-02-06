"""
Qdrant Client - Vector Database Connection
Quản lý kết nối tới Qdrant vector database
"""
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.http import models
from typing import Optional
from core.config import settings


class QdrantClientManager:
    """
    Singleton Qdrant client để quản lý kết nối
    """
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QdrantClientManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Khởi tạo Qdrant client"""
        if self._client is None:
            # Connect to Qdrant
            if settings.QDRANT_API_KEY:
                # Cloud version with API key
                self._client = QdrantClient(
                    host=settings.QDRANT_HOST,
                    port=settings.QDRANT_PORT,
                    api_key=settings.QDRANT_API_KEY
                )
            else:
                # Local version without API key
                self._client = QdrantClient(
                    host=settings.QDRANT_HOST,
                    port=settings.QDRANT_PORT
                )
            print(f"✅ Qdrant client initialized: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
    
    @property
    def client(self) -> QdrantClient:
        """Lấy Qdrant client instance"""
        return self._client
    
    async def ensure_collection_exists(self, collection_name: str = None) -> bool:
        """
        Đảm bảo collection tồn tại, nếu không thì tạo mới
        
        Args:
            collection_name: Tên collection (mặc định lấy từ settings)
        
        Returns:
            True nếu collection tồn tại hoặc tạo thành công
        """
        collection = collection_name or settings.QDRANT_COLLECTION_NAME
        
        try:
            # Check if collection exists
            collections = self._client.get_collections().collections
            collection_names = [col.name for col in collections]
            
            if collection not in collection_names:
                # Create collection with vector configuration
                self._client.create_collection(
                    collection_name=collection,
                    vectors_config=VectorParams(
                        size=settings.VECTOR_DIMENSION,  # Cohere embed-multilingual-v3.0 = 1024
                        distance=Distance.COSINE  # Cosine similarity
                    )
                )
                print(f"✅ Qdrant collection created: {collection}")
            else:
                print(f"✅ Qdrant collection already exists: {collection}")
            
            return True
        except Exception as e:
            print(f"❌ Qdrant collection error: {e}")
            return False
    
    async def connect(self):
        """Kết nối và setup collection"""
        await self.ensure_collection_exists()
    
    async def disconnect(self):
        """Ngắt kết nối"""
        print("✅ Qdrant client closed")


# Global instance
qdrant_client = QdrantClientManager()
