"""
Qdrant Service - Business Logic Layer
Xử lý các nghiệp vụ liên quan đến vector database: upsert, search, delete vectors
"""
from typing import List, Dict, Optional
from uuid import UUID
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from core.qdrant import qdrant_client
from core.config import settings


class QdrantService:
    """
    Service xử lý business logic cho Qdrant vector database
    """
    
    @staticmethod
    def upsert_vectors(
        points: List[Dict],
        collection_name: str = None
    ) -> bool:
        """
        Upsert vectors vào Qdrant collection
        
        Args:
            points: List of points to upsert, mỗi point có format:
                {
                    "id": str,              # UUID của chunk
                    "vector": List[float],  # Embedding vector
                    "payload": {            # Metadata
                        "document_id": str,
                        "chunk_id": str,
                        "chunk_text": str,
                        "chunk_index": int,
                        "user_id": str,
                        "file_name": str,
                        ...
                    }
                }
            collection_name: Tên collection (mặc định lấy từ settings)
        
        Returns:
            bool: True nếu upsert thành công
        
        Raises:
            Exception: Nếu upsert thất bại
        """
        collection = collection_name or settings.QDRANT_COLLECTION_NAME
        
        try:
            # Convert to PointStruct
            point_structs = [
                PointStruct(
                    id=point["id"],
                    vector=point["vector"],
                    payload=point["payload"]
                )
                for point in points
            ]
            
            # Upsert to Qdrant
            qdrant_client.client.upsert(
                collection_name=collection,
                points=point_structs
            )
            
            return True
        
        except Exception as e:
            raise Exception(f"Qdrant upsert error: {e}")
    
    @staticmethod
    def search_similar(
        query_vector: List[float],
        limit: int = 5,
        score_threshold: float = 0.7,
        filter_conditions: Optional[Dict] = None,
        collection_name: str = None
    ) -> List[Dict]:
        """
        Tìm kiếm vectors tương tự
        
        Args:
            query_vector: Query embedding vector
            limit: Số lượng kết quả trả về
            score_threshold: Ngưỡng similarity score (0-1)
            filter_conditions: Filter conditions, ví dụ:
                {
                    "user_id": "uuid",
                    "document_id": "uuid"
                }
            collection_name: Tên collection (mặc định lấy từ settings)
        
        Returns:
            List[Dict]: Danh sách kết quả, mỗi item có format:
                {
                    "id": str,
                    "score": float,
                    "payload": dict
                }
        
        Raises:
            Exception: Nếu search thất bại
        """
        collection = collection_name or settings.QDRANT_COLLECTION_NAME
        
        try:
            # Build filter if provided
            query_filter = None
            if filter_conditions:
                must_conditions = []
                for key, value in filter_conditions.items():
                    must_conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                    )
                query_filter = Filter(must=must_conditions)
            
            # Search
            search_results = qdrant_client.client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter
            )
            
            # Format results
            results = []
            for hit in search_results:
                results.append({
                    "id": hit.id,
                    "score": hit.score,
                    "payload": hit.payload
                })
            
            return results
        
        except Exception as e:
            raise Exception(f"Qdrant search error: {e}")
    
    @staticmethod
    def delete_vectors(
        point_ids: List[str],
        collection_name: str = None
    ) -> bool:
        """
        Xóa vectors từ collection
        
        Args:
            point_ids: List of point IDs to delete
            collection_name: Tên collection (mặc định lấy từ settings)
        
        Returns:
            bool: True nếu delete thành công
        
        Raises:
            Exception: Nếu delete thất bại
        """
        collection = collection_name or settings.QDRANT_COLLECTION_NAME
        
        try:
            qdrant_client.client.delete(
                collection_name=collection,
                points_selector=point_ids
            )
            return True
        
        except Exception as e:
            raise Exception(f"Qdrant delete error: {e}")
    
    @staticmethod
    def delete_by_filter(
        filter_conditions: Dict,
        collection_name: str = None
    ) -> bool:
        """
        Xóa vectors theo filter conditions
        
        Args:
            filter_conditions: Filter conditions, ví dụ:
                {
                    "document_id": "uuid"
                }
            collection_name: Tên collection (mặc định lấy từ settings)
        
        Returns:
            bool: True nếu delete thành công
        
        Raises:
            Exception: Nếu delete thất bại
        """
        collection = collection_name or settings.QDRANT_COLLECTION_NAME
        
        try:
            # Build filter
            must_conditions = []
            for key, value in filter_conditions.items():
                must_conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )
            query_filter = Filter(must=must_conditions)
            
            # Delete
            qdrant_client.client.delete(
                collection_name=collection,
                points_selector=query_filter
            )
            return True
        
        except Exception as e:
            raise Exception(f"Qdrant delete by filter error: {e}")


# Global instance
qdrant_service = QdrantService()
