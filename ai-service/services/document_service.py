"""
Document Processing Service
Xử lý documents: load, split, embed, và lưu vào Qdrant
"""
from typing import List, Dict, Any
import tempfile
import os
import logging
import time
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain.schema import Document as LangchainDocument
from qdrant_client.models import PointStruct
import pandas as pd

from core.config import settings
from core.qdrant import qdrant_manager
from services.embedding_service import embedding_service

logger = logging.getLogger(__name__)


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

    # ------------------------------------------------------------------
    # Gemini Vision OCR helper – used for both images and scanned PDFs
    # ------------------------------------------------------------------
    def _ocr_image_with_gemini(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        context_hint: str = "",
        max_retries: int = 3,
    ) -> str:
        """
        Use Gemini Vision (multimodal) to extract ALL text and describe
        visual content from an image.  Retries on transient errors.

        Args:
            image_bytes: raw image bytes (JPEG / PNG / WebP / HEIC)
            mime_type: MIME type of the image
            context_hint: optional hint (e.g. "Page 3 of a chemistry textbook")
            max_retries: number of attempts before giving up

        Returns:
            Extracted text (may be empty string on total failure)
        """
        from core.model_manager import model_manager

        vision_prompt = (
            "You are an expert document digitization and image analysis AI.\n"
            "Your task is to analyze this image thoroughly and extract ALL information:\n\n"
            "1. **Text extraction**: Read and transcribe ALL text, numbers, formulas, "
            "and symbols visible in the image. Preserve the original language.\n"
            "2. **Tables**: If there are tables, reproduce them accurately in Markdown table format.\n"
            "3. **Diagrams/Charts**: Describe any diagrams, charts, graphs, or figures in detail, "
            "including labels, axes, values, and relationships shown.\n"
            "4. **Visual content**: Describe any photos, illustrations, or visual elements.\n"
            "5. **Mathematical formulas**: Reproduce any math formulas using LaTeX notation.\n"
            "6. **Layout**: Maintain the logical reading order and paragraph structure.\n\n"
            "Output everything in a well-structured format. "
            "If the image contains text in Vietnamese, keep it in Vietnamese. "
            "If the image contains text in English, keep it in English.\n"
            "Do NOT add commentary like 'This image shows...' — just output the content directly."
        )
        if context_hint:
            vision_prompt += f"\n\nContext: {context_hint}"

        last_error = None
        for attempt in range(max_retries):
            try:
                result = model_manager.generate_text_from_image(
                    prompt=vision_prompt,
                    image_bytes=image_bytes,
                    mime_type=mime_type,
                    temperature=0.2,  # Low temperature for faithful extraction
                )
                if result and result.strip():
                    logger.info(f"✅ Vision OCR succeeded (attempt {attempt+1}), extracted {len(result)} chars")
                    return result.strip()
                else:
                    logger.warning(f"⚠️ Vision OCR returned empty text (attempt {attempt+1})")
                    last_error = "Empty response from Vision API"
            except Exception as e:
                last_error = str(e)
                logger.warning(f"⚠️ Vision OCR attempt {attempt+1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))  # Back-off: 2s, 4s, 6s

        logger.error(f"❌ Vision OCR failed after {max_retries} attempts. Last error: {last_error}")
        return ""

    # ------------------------------------------------------------------
    # Scanned PDF → images → OCR via PyMuPDF + Gemini Vision
    # ------------------------------------------------------------------
    def _ocr_pdf_pages(self, tmp_file_path: str, file_name: str) -> List[LangchainDocument]:
        """
        Convert each page of a PDF to an image and run Gemini Vision OCR.
        Returns a list of LangchainDocuments (one per page that had content).
        """
        import fitz  # PyMuPDF

        documents = []
        try:
            pdf_doc = fitz.open(tmp_file_path)
            total_pages = len(pdf_doc)
            logger.info(f"📄 OCR scanning {total_pages} pages of '{file_name}'...")

            for i, page in enumerate(pdf_doc):
                # Render page at 200 DPI for good OCR quality
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("jpeg")

                context_hint = f"Page {i+1}/{total_pages} of document '{file_name}'"
                vision_text = self._ocr_image_with_gemini(
                    image_bytes=img_bytes,
                    mime_type="image/jpeg",
                    context_hint=context_hint,
                )

                if vision_text:
                    doc = LangchainDocument(
                        page_content=f"[SCAN PAGE {i+1}/{total_pages}]\n{vision_text}",
                        metadata={
                            "file_name": file_name,
                            "file_type": ".pdf",
                            "pre_chunked": False,
                            "source": file_name,
                            "page": i,
                            "is_image_ocr": True,
                            "ocr_method": "gemini_vision",
                        }
                    )
                    documents.append(doc)
                    logger.info(f"  ✅ Page {i+1}: extracted {len(vision_text)} chars")
                else:
                    logger.warning(f"  ⚠️ Page {i+1}: no text extracted")

            pdf_doc.close()
        except Exception as e:
            logger.error(f"❌ PDF OCR failed for '{file_name}': {e}")
            import traceback
            logger.error(traceback.format_exc())

        return documents

    # ------------------------------------------------------------------
    # Main entry: load document from raw bytes
    # ------------------------------------------------------------------
    def load_document_from_bytes(
        self,
        file_data: bytes,
        file_name: str,
        file_type: str
    ) -> List[LangchainDocument]:
        """
        Load document từ bytes data và tiền xử lý/chunking riêng cho từng định dạng.
        Supports: PDF (text + scanned), DOCX, images, code files, CSV/XLSX, plain text.
        """
        from langchain.text_splitter import Language
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp_file:
                tmp_file.write(file_data)
                tmp_file_path = tmp_file.name
            
            ext = os.path.splitext(file_name)[1].lower()
            code_extensions = [".py", ".java", ".js", ".cpp", ".ts", ".md", ".html", ".css"]
            image_extensions = [".jpg", ".jpeg", ".png", ".webp", ".heic"]
            
            documents = []
            
            # ==================== PDF ====================
            if file_type in ["application/pdf", ".pdf"] or ext == ".pdf":
                loader = PyPDFLoader(tmp_file_path)
                documents = loader.load()
                
                # Check if text extraction was successful
                total_text = "".join(d.page_content for d in documents).strip()
                
                # If very little text → scanned/image-based PDF → OCR each page
                if len(total_text) < 150:
                    logger.info(f"📄 PDF '{file_name}' has very little text ({len(total_text)} chars). "
                                f"Treating as scanned PDF → Vision OCR...")
                    documents = self._ocr_pdf_pages(tmp_file_path, file_name)
                    
                    if not documents:
                        # Last resort: treat entire PDF text (even if short) as content
                        if total_text:
                            documents = [LangchainDocument(
                                page_content=total_text,
                                metadata={
                                    "file_name": file_name, "file_type": ext,
                                    "pre_chunked": False, "source": file_name,
                                    "is_image_ocr": True,
                                }
                            )]
                            logger.warning(f"⚠️ OCR failed, using original sparse text ({len(total_text)} chars)")
                else:
                    for d in documents:
                        d.metadata.update({
                            "file_name": file_name, "file_type": ext,
                            "pre_chunked": False, "source": file_name
                        })

            # ==================== IMAGE FILES ====================
            elif (file_type and file_type.startswith("image/")) or ext in image_extensions:
                logger.info(f"🖼️ Image '{file_name}' detected (type={file_type}, ext={ext}). Running Vision OCR...")
                
                # Determine correct MIME type
                mime_map = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".webp": "image/webp",
                    ".heic": "image/heic",
                }
                if file_type and file_type.startswith("image/"):
                    m_type = file_type
                else:
                    m_type = mime_map.get(ext, "image/jpeg")

                vision_text = self._ocr_image_with_gemini(
                    image_bytes=file_data,
                    mime_type=m_type,
                    context_hint=f"Standalone image file: {file_name}",
                )

                if vision_text:
                    documents = [LangchainDocument(
                        page_content=f"[IMAGE: {file_name}]\n{vision_text}",
                        metadata={
                            "source": file_name,
                            "file_name": file_name,
                            "file_type": ext,
                            "pre_chunked": False,
                            "is_image_ocr": True,
                            "ocr_method": "gemini_vision",
                        }
                    )]
                    logger.info(f"✅ Image OCR complete: {len(vision_text)} chars extracted from '{file_name}'")
                else:
                    # Even on failure, create a minimal document so processing doesn't 400
                    logger.error(f"❌ Image OCR returned no text for '{file_name}'. "
                                 f"Creating placeholder document.")
                    documents = [LangchainDocument(
                        page_content=f"[IMAGE: {file_name}]\n"
                                     f"(Hình ảnh đã được tải lên nhưng không thể trích xuất nội dung văn bản. "
                                     f"File: {file_name})",
                        metadata={
                            "source": file_name,
                            "file_name": file_name,
                            "file_type": ext,
                            "pre_chunked": False,
                            "is_image_ocr": True,
                            "ocr_failed": True,
                        }
                    )]

            # ==================== DOCX ====================
            elif file_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"] or ext == ".docx":
                loader = Docx2txtLoader(tmp_file_path)
                documents = loader.load()
                for d in documents:
                    d.metadata.update({"file_name": file_name, "file_type": ext, "pre_chunked": False, "source": file_name})
                    
            # ==================== CODE FILES ====================
            elif ext in code_extensions:
                with open(tmp_file_path, 'r', encoding='utf-8', errors='replace') as f:
                    text = f.read()
                
                lang_map = {
                    ".py": Language.PYTHON, ".java": Language.JAVA, ".js": Language.JS,
                    ".cpp": Language.CPP, ".ts": Language.TS, ".html": Language.HTML,
                    ".md": Language.MARKDOWN
                }
                
                lc_lang = lang_map.get(ext)
                if lc_lang:
                    splitter = RecursiveCharacterTextSplitter.from_language(
                        language=lc_lang, chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP
                    )
                else:
                    splitter = RecursiveCharacterTextSplitter(chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)
                
                chunks = splitter.create_documents([text])
                for chunk in chunks:
                    chunk.metadata.update({
                        "file_name": file_name,
                        "file_type": ext,
                        "pre_chunked": True,
                        "is_code": True,
                        "source": file_name
                    })
                    documents.append(chunk)

            # ==================== CSV / XLSX ====================
            elif ext in [".csv", ".xlsx"]:
                if ext == ".csv":
                    df = pd.read_csv(tmp_file_path)
                    docs = self._process_dataframe(df, file_name, ext, title="CSV Data")
                    documents.extend(docs)
                else:
                    xls = pd.ExcelFile(tmp_file_path)
                    for sheet_name in xls.sheet_names:
                        df = pd.read_excel(tmp_file_path, sheet_name=sheet_name)
                        docs = self._process_dataframe(df, file_name, ext, title=f"Sheet: {sheet_name}", is_sheet=True)
                        documents.extend(docs)

            # ==================== PLAIN TEXT / OTHER ====================
            else:
                with open(tmp_file_path, 'r', encoding='utf-8', errors='replace') as f:
                    text = f.read()
                documents = [LangchainDocument(
                    page_content=text,
                    metadata={"source": file_name, "file_name": file_name, "file_type": ext, "pre_chunked": False}
                )]
            
            os.unlink(tmp_file_path)
            return documents
            
        except Exception as e:
            if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
            raise Exception(f"Document loading error: {e}")

    def _process_dataframe(self, df, file_name: str, ext: str, title: str, is_sheet: bool = False) -> List[LangchainDocument]:
        chunk_size = 15 # Group by 15 rows
        docs = []
        for i in range(0, len(df), chunk_size):
            chunk_df = df.iloc[i:i+chunk_size]
            md_table = chunk_df.to_markdown(index=False)
            
            content = ""
            if is_sheet:
                content += f"### {title}\n\n"
            content += md_table
            
            doc = LangchainDocument(
                page_content=content,
                metadata={
                    "source": file_name,
                    "file_name": file_name,
                    "file_type": ext,
                    "is_table": True,
                    "title": title,
                    "pre_chunked": True
                }
            )
            docs.append(doc)
        return docs

    def split_documents(
        self,
        documents: List[LangchainDocument]
    ) -> List[LangchainDocument]:
        """
        Split documents thành các chunks nhỏ và format kết quả dưới dạng Markdown Embedding chuẩn
        """
        docs_to_split = [doc for doc in documents if not doc.metadata.get("pre_chunked")]
        pre_chunked_docs = [doc for doc in documents if doc.metadata.get("pre_chunked")]
        
        split_docs = []
        if docs_to_split:
            split_docs = self.text_splitter.split_documents(docs_to_split)
        
        all_chunks = split_docs + pre_chunked_docs
        
        final_chunks = []
        for chunk in all_chunks:
            raw_content = chunk.page_content.strip() if getattr(chunk, 'page_content', None) else ""
            
            # Skip completely empty chunks (e.g. from scanned PDFs)
            if not raw_content:
                continue

            file_name = chunk.metadata.get("file_name", chunk.metadata.get("source", "unknown"))
            file_type = chunk.metadata.get("file_type", "")
            if not file_type and "." in file_name:
                file_type = "." + file_name.split(".")[-1]
            
            is_code = chunk.metadata.get("is_code", False)
            is_image_ocr = chunk.metadata.get("is_image_ocr", False)
            title = chunk.metadata.get("title", file_name)
            
            if is_code:
                lang = file_type.replace(".", "").lower()
                lang_ext_map = {
                    "md": "markdown", "js": "javascript", "ts": "typescript", "py": "python"
                }
                lang = lang_ext_map.get(lang, lang)
                formatted_body = f"[SOURCE CODE]: {file_name}\n"
                formatted_body += f"```{lang}\n{raw_content}\n```"
            else:
                formatted_body = raw_content
            
            # Build metadata header with source type info
            source_type = "OCR/Vision" if is_image_ocr else "MinIO"
            final_content = (
                f'Metadata: {{filename: "{file_name}", file_type: "{file_type}", source: "{source_type}"}}\n'
                f'Content: > [{title}]\n'
                f'{formatted_body}'
            )
            
            chunk.page_content = final_content
            final_chunks.append(chunk)
            
        return final_chunks
    
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
                    "tags": metadata.get("tags", []),
                    "is_image_ocr": chunk_data.get("chunk_metadata", {}).get("is_image_ocr", False),
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
