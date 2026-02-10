"""
Embedding Service
Xử lý việc generate embeddings từ texts bằng Cohere API
"""
from typing import List
import cohere
from core.config import settings


class EmbeddingService:
    """Service xử lý embedding generation"""
    
    def __init__(self):
        """Initialize Cohere client"""
        self.cohere_client = cohere.Client(settings.COHERE_API_KEY)
        self.model = settings.COHERE_EMBEDDING_MODEL
    
    def embed_texts(
        self,
        texts: List[str],
        input_type: str = "search_document"
    ) -> List[List[float]]:
        """
        Generate embeddings cho danh sách texts
        
        Args:
            texts: Danh sách texts cần embed
            input_type: "search_document" (cho lưu trữ) hoặc "search_query" (cho query)
        
        Returns:
            List[List[float]]: Danh sách embedding vectors
        
        Raises:
            Exception: Nếu embedding thất bại
        """
        try:
            # Validate input_type
            if input_type not in ["search_document", "search_query"]:
                input_type = "search_document"
            
            # Call Cohere API
            response = self.cohere_client.embed(
                texts=texts,
                model=self.model,
                input_type=input_type
            )
            
            return response.embeddings
        
        except Exception as e:
            raise Exception(f"Cohere embedding error: {e}")
    
    def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding cho search query
        
        Args:
            query: Query text
        
        Returns:
            List[float]: Embedding vector
        """
        embeddings = self.embed_texts([query], input_type="search_query")
        return embeddings[0]
    
    def get_vector_dimension(self) -> int:
        """Get vector dimension của model"""
        return settings.VECTOR_DIMENSION


# Global instance
embedding_service = EmbeddingService()
