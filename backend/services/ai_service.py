"""
AI Service HTTP Client
Gọi AI Service microservice thay vì xử lý trực tiếp
"""
from typing import List, Dict, Optional
from uuid import UUID
import httpx
from sqlalchemy.orm import Session

from core.config import settings
from models.documents import Document, DocumentChunk, DocumentEmbedding
from services.minio_service import minio_service


class AIService:
    """
    HTTP Client cho AI Service microservice
    """
    
    def __init__(self):
        """Initialize AI Service URL"""
        self.ai_service_url = getattr(settings, 'AI_SERVICE_URL', 'http://ai-service:8001')
        self.timeout = 120.0  # 2 minutes timeout for processing
    
    async def generate_embeddings(
        self,
        texts: List[str],
        input_type: str = "search_document"
    ) -> List[List[float]]:
        """
        Generate embeddings qua AI Service
        
        Args:
            texts: Danh sách texts cần embed
            input_type: "search_document" hoặc "search_query"
        
        Returns:
            List[List[float]]: Danh sách embedding vectors
        
        Raises:
            Exception: Nếu AI Service request thất bại
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.ai_service_url}/api/embed",
                    json={
                        "texts": texts,
                        "input_type": input_type
                    }
                )
                response.raise_for_status()
                data = response.json()
                return data["embeddings"]
        
        except Exception as e:
            raise Exception(f"AI Service embedding error: {e}")
    
    def process_document(
        self,
        document_id: UUID,
        db: Session
    ) -> bool:
        """
        Xử lý document qua AI Service: load từ MinIO -> forward to AI Service
        AI Service sẽ xử lý: split -> embed -> lưu Qdrant
        Backend chỉ lưu chunks vào PostgreSQL
        
        Args:
            document_id: ID của document trong database
            db: Database session
        
        Returns:
            bool: True nếu xử lý thành công
        
        Raises:
            Exception: Nếu xử lý thất bại
        """
        import asyncio
        
        try:
            # 1. Lấy document từ database
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                raise Exception(f"Document {document_id} not found")
            
            # Update status
            document.processing_status = "processing"
            db.commit()
            
            # 2. Download file từ MinIO
            object_name = document.file_path.split("/", 1)[1]  # Remove bucket name
            file_data = minio_service.download_file(object_name)
            
            # 3. Forward to AI Service for processing
            result = asyncio.run(self._process_document_async(
                file_data=file_data,
                file_name=document.file_name,
                file_type=document.file_type,
                document_id=str(document_id),
                user_id=str(document.user_id),
                metadata={
                    "title": document.title,
                    "category": document.category,
                    "tags": document.tags
                }
            ))
            
            if not result["success"]:
                raise Exception(result.get("message", "AI Service processing failed"))
            
            # 4. AI Service đã upsert vào Qdrant, giờ lưu chunks vào PostgreSQL
            # Note: AI Service trả về chunks_count, nhưng không trả về chunk data
            # Để đơn giản, ta sẽ fetch chunks từ Qdrant hoặc có thể AI Service trả về
            
            # Update document status
            document.is_processed = True
            document.processing_status = "completed"
            db.commit()
            
            print(f"✅ Document {document_id} processed successfully via AI Service")
            return True
        
        except Exception as e:
            # Update status to failed
            if document:
                document.processing_status = "failed"
                db.commit()
            
            print(f"❌ Document processing error: {e}")
            raise Exception(f"Document processing failed: {e}")
    
    async def _process_document_async(
        self,
        file_data: bytes,
        file_name: str,
        file_type: str,
        document_id: str,
        user_id: str,
        metadata: Dict
    ) -> Dict:
        """
        Async helper to call AI Service
        """
        import json
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Prepare multipart form data
                files = {
                    'file': (file_name, file_data, file_type)
                }
                data = {
                    'document_id': document_id,
                    'user_id': user_id,
                    'metadata': json.dumps(metadata)
                }
                
                response = await client.post(
                    f"{self.ai_service_url}/api/documents/process",
                    files=files,
                    data=data
                )
                response.raise_for_status()
                return response.json()
        
        except Exception as e:
            return {
                "success": False,
                "message": f"AI Service request failed: {e}"
            }
    
    async def delete_document_vectors(
        self,
        document_id: UUID,
        db: Session
    ) -> bool:
        """
        Xóa vectors của document từ Qdrant qua AI Service
        
        Args:
            document_id: ID của document
            db: Database session
        
        Returns:
            bool: True nếu xóa thành công
        """
        try:
            await self._delete_document_async(str(document_id))
            return True
        
        except Exception as e:
            raise Exception(f"Vector deletion error: {e}")
    
    async def _delete_document_async(self, document_id: str) -> bool:
        """Async helper to delete vectors via AI Service"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.ai_service_url}/api/documents/vectors/{document_id}"
                )
                response.raise_for_status()
                return True
        except Exception as e:
            raise Exception(f"AI Service delete request failed: {e}")
    
    async def query_rag(
        self,
        question: str,
        user_id: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = 5,
        score_threshold: float = 0.7
    ) -> Dict:
        """
        Query RAG system qua AI Service
        
        Args:
            question: Câu hỏi
            user_id: User ID
            document_ids: Optional document IDs
            top_k: Số contexts
            score_threshold: Score threshold
        
        Returns:
            Dict với answer, contexts, metadata
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.ai_service_url}/api/rag/query",
                    json={
                        "question": question,
                        "user_id": user_id,
                        "document_ids": document_ids,
                        "top_k": top_k,
                        "score_threshold": score_threshold,
                        "include_sources": True
                    }
                )
                response.raise_for_status()
                return response.json()
        
        except Exception as e:
            raise Exception(f"RAG query error: {e}")
    
    async def chat_with_ai(
        self,
        messages: List[Dict[str, str]],
        user_id: str,
        document_ids: Optional[List[str]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict:
        """
        Chat với AI có document context qua AI Service
        
        Args:
            messages: Chat history
            user_id: User ID
            document_ids: Optional document IDs
            temperature: Temperature
            max_tokens: Max tokens
        
        Returns:
            Dict với message, contexts, metadata
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.ai_service_url}/api/rag/chat",
                    json={
                        "messages": messages,
                        "user_id": user_id,
                        "document_ids": document_ids,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": False
                    }
                )
                response.raise_for_status()
                return response.json()
        
        except Exception as e:
            raise Exception(f"Chat error: {e}")


# Global instance
ai_service = AIService()
