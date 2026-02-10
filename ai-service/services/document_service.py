"""
Document Processing Service
Xử lý documents: load, split, embed, và lưu vào Qdrant
"""
from typing import List, Dict, Any
import tempfile
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain.schema import Document as LangchainDocument
from qdrant_client.models import PointStruct

from core.config import settings
from core.qdrant import qdrant_manager
from services.embedding_service import embedding_service


class DocumentProcessingService:
    """Service xử lý document processing pipeline"""
    
    def __init__(self):
        """Initialize text splitter"""
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
    
    def load_document_from_bytes(
        self,
        file_data: bytes,
        file_name: str,
        file_type: str
    ) -> List[LangchainDocument]:
        """
        Load document từ bytes data
        
        Args:
            file_data: File binary data
            file_name: Tên file
            file_type: MIME type hoặc extension
        
        Returns:
            List[LangchainDocument]: Danh sách documents
        
        Raises:
            Exception: Nếu load thất bại hoặc file type không support
        """
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=os.path.splitext(file_name)[1]
            ) as tmp_file:
                tmp_file.write(file_data)
                tmp_file_path = tmp_file.name
            
            # Load based on file type
            if file_type in ["application/pdf", ".pdf"]:
                loader = PyPDFLoader(tmp_file_path)
            elif file_type in [
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".docx"
            ]:
                loader = Docx2txtLoader(tmp_file_path)
            else:
                # For text files
                with open(tmp_file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                os.unlink(tmp_file_path)
                return [LangchainDocument(
                    page_content=text,
                    metadata={"source": file_name}
                )]
            
            # Load documents
            documents = loader.load()
            
            # Clean up temporary file
            os.unlink(tmp_file_path)
            
            return documents
        
        except Exception as e:
            raise Exception(f"Document loading error: {e}")
    
    def split_documents(
        self,
        documents: List[LangchainDocument]
    ) -> List[LangchainDocument]:
        """
        Split documents thành các chunks nhỏ
        
        Args:
            documents: List of LangchainDocument
        
        Returns:
            List[LangchainDocument]: Danh sách chunks
        """
        return self.text_splitter.split_documents(documents)
    
    def prepare_chunks_data(
        self,
        chunks: List[LangchainDocument],
        document_id: str,
        user_id: str,
        file_name: str,
        metadata: Dict[str, Any]
    ) -> tuple[List[Dict], List[str]]:
        """
        Prepare chunks data for embedding
        
        Args:
            chunks: LangChain document chunks
            document_id: Document ID
            user_id: User ID
            file_name: File name
            metadata: Additional metadata
        
        Returns:
            tuple: (chunk_records data, chunk_texts)
        """
        chunk_records = []
        chunk_texts = []
        
        for idx, chunk in enumerate(chunks):
            chunk_data = {
                "chunk_index": idx,
                "chunk_text": chunk.page_content,
                "chunk_metadata": chunk.metadata,
                "token_count": len(chunk.page_content) // 4,
                "document_id": document_id,
                "user_id": user_id,
                "file_name": file_name
            }
            
            chunk_records.append(chunk_data)
            chunk_texts.append(chunk.page_content)
        
        return chunk_records, chunk_texts
    
    def upsert_to_qdrant(
        self,
        chunk_ids: List[str],
        embeddings: List[List[float]],
        chunks_data: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Upsert vectors vào Qdrant
        
        Args:
            chunk_ids: List of chunk IDs
            embeddings: List of embedding vectors
            chunks_data: List of chunk data dicts
            metadata: Document metadata
        
        Returns:
            bool: True if successful
        """
        try:
            points = []
            
            for chunk_id, embedding, chunk_data in zip(
                chunk_ids, embeddings, chunks_data
            ):
                payload = {
                    "document_id": chunk_data["document_id"],
                    "chunk_id": chunk_id,
                    "chunk_text": chunk_data["chunk_text"],
                    "chunk_index": chunk_data["chunk_index"],
                    "user_id": chunk_data["user_id"],
                    "file_name": chunk_data["file_name"],
                    "title": metadata.get("title", ""),
                    "category": metadata.get("category", ""),
                    "tags": metadata.get("tags", [])
                }
                
                point = PointStruct(
                    id=chunk_id,
                    vector=embedding,
                    payload=payload
                )
                
                points.append(point)
            
            # Upsert to Qdrant
            qdrant_manager.client.upsert(
                collection_name=qdrant_manager.collection_name,
                points=points
            )
            
            return True
        
        except Exception as e:
            raise Exception(f"Qdrant upsert error: {e}")


# Global instance
document_processing_service = DocumentProcessingService()
