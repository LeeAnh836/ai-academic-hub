"""
AI Service - Business Logic Layer
Xử lý AI Processing Pipeline: document loading, splitting, embedding, và lưu vào database
"""
from typing import List, Dict, BinaryIO
from uuid import UUID
import io
import tempfile
import os
from sqlalchemy.orm import Session

import cohere
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain.schema import Document as LangchainDocument

from core.config import settings
from models.documents import Document, DocumentChunk, DocumentEmbedding
from services.minio_service import minio_service
from services.qdrant_service import qdrant_service


class AIService:
    """
    Service xử lý AI processing pipeline
    """
    
    def __init__(self):
        """Khởi tạo Cohere client"""
        self.cohere_client = cohere.Client(settings.COHERE_API_KEY)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,        # 1000 characters per chunk
            chunk_overlap=200,      # 200 characters overlap
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
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp_file:
                tmp_file.write(file_data)
                tmp_file_path = tmp_file.name
            
            # Load based on file type
            if file_type in ["application/pdf", ".pdf"]:
                loader = PyPDFLoader(tmp_file_path)
            elif file_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"]:
                loader = Docx2txtLoader(tmp_file_path)
            else:
                # For text files
                with open(tmp_file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                os.unlink(tmp_file_path)
                return [LangchainDocument(page_content=text, metadata={"source": file_name})]
            
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
    
    def generate_embeddings(
        self,
        texts: List[str]
    ) -> List[List[float]]:
        """
        Generate embeddings cho danh sách texts bằng Cohere
        
        Args:
            texts: Danh sách texts cần embed
        
        Returns:
            List[List[float]]: Danh sách embedding vectors
        
        Raises:
            Exception: Nếu embedding thất bại
        """
        try:
            # Call Cohere API
            response = self.cohere_client.embed(
                texts=texts,
                model=settings.COHERE_EMBEDDING_MODEL,
                input_type="search_document"  # For storing in vector DB
            )
            
            return response.embeddings
        
        except Exception as e:
            raise Exception(f"Cohere embedding error: {e}")
    
    def process_document(
        self,
        document_id: UUID,
        db: Session
    ) -> bool:
        """
        Xử lý document: load từ MinIO -> split -> embed -> lưu vào Postgres + Qdrant
        
        Args:
            document_id: ID của document trong database
            db: Database session
        
        Returns:
            bool: True nếu xử lý thành công
        
        Raises:
            Exception: Nếu xử lý thất bại
        """
        try:
            # 1. Lấy document từ database
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                raise Exception(f"Document {document_id} not found")
            
            # Update status
            document.processing_status = "processing"
            db.commit()
            
            # 2. Download file từ MinIO
            # file_path format: "bucket/user_id/filename"
            object_name = document.file_path.split("/", 1)[1]  # Remove bucket name
            file_data = minio_service.download_file(object_name)
            
            # 3. Load document
            langchain_docs = self.load_document_from_bytes(
                file_data=file_data,
                file_name=document.file_name,
                file_type=document.file_type
            )
            
            # 4. Split thành chunks
            chunks = self.split_documents(langchain_docs)
            
            if not chunks:
                raise Exception("No chunks generated from document")
            
            # 5. Lưu chunks vào PostgreSQL
            chunk_records = []
            chunk_texts = []
            
            for idx, chunk in enumerate(chunks):
                chunk_record = DocumentChunk(
                    document_id=document_id,
                    chunk_index=idx,
                    chunk_text=chunk.page_content,
                    chunk_metadata=chunk.metadata,
                    token_count=len(chunk.page_content) // 4  # Rough estimate
                )
                db.add(chunk_record)
                chunk_records.append(chunk_record)
                chunk_texts.append(chunk.page_content)
            
            db.flush()  # Flush to get chunk IDs
            
            # 6. Generate embeddings
            embeddings = self.generate_embeddings(chunk_texts)
            
            # 7. Prepare data for Qdrant
            qdrant_points = []
            
            for chunk_record, embedding in zip(chunk_records, embeddings):
                # Lưu metadata vào PostgreSQL
                embedding_record = DocumentEmbedding(
                    chunk_id=chunk_record.id,
                    document_id=document_id,
                    qdrant_point_id=str(chunk_record.id),
                    embedding_model=settings.COHERE_EMBEDDING_MODEL,
                    vector_dimension=len(embedding)
                )
                db.add(embedding_record)
                
                # Prepare point for Qdrant
                qdrant_points.append({
                    "id": str(chunk_record.id),
                    "vector": embedding,
                    "payload": {
                        "document_id": str(document_id),
                        "chunk_id": str(chunk_record.id),
                        "chunk_text": chunk_record.chunk_text,
                        "chunk_index": chunk_record.chunk_index,
                        "user_id": str(document.user_id),
                        "file_name": document.file_name,
                        "title": document.title,
                        "category": document.category,
                        "tags": document.tags
                    }
                })
            
            # 8. Upsert vào Qdrant
            qdrant_service.upsert_vectors(qdrant_points)
            
            # 9. Update document status
            document.is_processed = True
            document.processing_status = "completed"
            db.commit()
            
            print(f"✅ Document {document_id} processed successfully: {len(chunks)} chunks")
            return True
        
        except Exception as e:
            # Update status to failed
            if document:
                document.processing_status = "failed"
                db.commit()
            
            print(f"❌ Document processing error: {e}")
            raise Exception(f"Document processing failed: {e}")
    
    def delete_document_vectors(
        self,
        document_id: UUID,
        db: Session
    ) -> bool:
        """
        Xóa vectors của document từ Qdrant và PostgreSQL
        
        Args:
            document_id: ID của document
            db: Database session
        
        Returns:
            bool: True nếu xóa thành công
        """
        try:
            # Delete from Qdrant by document_id filter
            qdrant_service.delete_by_filter({"document_id": str(document_id)})
            
            # PostgreSQL sẽ tự động xóa chunks và embeddings nhờ cascade delete
            
            return True
        
        except Exception as e:
            raise Exception(f"Vector deletion error: {e}")


# Global instance
ai_service = AIService()
