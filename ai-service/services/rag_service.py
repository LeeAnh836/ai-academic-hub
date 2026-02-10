"""
RAG Service
Retrieval Augmented Generation - Tìm kiếm context và generate câu trả lời
"""
from typing import List, Optional, Dict, Any
import time
import cohere
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

from core.config import settings
from core.qdrant import qdrant_manager
from services.embedding_service import embedding_service


class RAGService:
    """Service xử lý RAG pipeline"""
    
    def __init__(self):
        """Initialize Cohere LLM client"""
        self.cohere_client = cohere.Client(settings.COHERE_API_KEY)
        self.llm_model = settings.COHERE_LLM_MODEL
    
    def search_relevant_contexts(
        self,
        query: str,
        user_id: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = 5,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm contexts liên quan từ Qdrant
        
        Args:
            query: Câu hỏi/query
            user_id: User ID để filter
            document_ids: Optional list of document IDs để filter
            top_k: Số lượng kết quả
            score_threshold: Ngưỡng similarity score
        
        Returns:
            List[Dict]: Danh sách contexts với metadata
        """
        try:
            # Generate query embedding
            query_vector = embedding_service.embed_query(query)
            
            # Build filter
            filter_conditions = [
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id)
                )
            ]
            
            # Add document_ids filter if provided
            if document_ids:
                filter_conditions.append(
                    FieldCondition(
                        key="document_id",
                        match=MatchAny(any=document_ids)
                    )
                )
            
            query_filter = Filter(must=filter_conditions) if filter_conditions else None
            
            # Search in Qdrant
            search_results = qdrant_manager.client.search(
                collection_name=qdrant_manager.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=score_threshold
            )
            
            # Format results
            contexts = []
            for result in search_results:
                context = {
                    "chunk_id": result.id,
                    "score": result.score,
                    "chunk_text": result.payload.get("chunk_text", ""),
                    "chunk_index": result.payload.get("chunk_index", 0),
                    "document_id": result.payload.get("document_id", ""),
                    "file_name": result.payload.get("file_name", ""),
                    "title": result.payload.get("title", ""),
                }
                contexts.append(context)
            
            return contexts
        
        except Exception as e:
            raise Exception(f"Context search error: {e}")
    
    def build_rag_prompt(
        self,
        question: str,
        contexts: List[Dict[str, Any]]
    ) -> str:
        """
        Build prompt cho RAG với contexts
        
        Args:
            question: Câu hỏi của user
            contexts: Danh sách contexts từ vector search
        
        Returns:
            str: Prompt đầy đủ
        """
        # Build context string
        context_parts = []
        for idx, ctx in enumerate(contexts, 1):
            context_parts.append(
                f"[TÀI LIỆU {idx}] - {ctx['file_name']}\n{ctx['chunk_text']}\n"
            )
        
        context_str = "\n".join(context_parts)
        
        # Build full prompt
        prompt = f"""Bạn là trợ lý học tập thông minh, giúp sinh viên trả lời câu hỏi dựa trên tài liệu học tập.

NGUYÊN TẮC:
- Trả lời dựa CHÍNH XÁC vào nội dung tài liệu được cung cấp
- Nếu không tìm thấy thông tin trong tài liệu, hãy nói rõ "Tôi không tìm thấy thông tin này trong tài liệu"
- Trích dẫn nguồn khi trả lời (ví dụ: "Theo tài liệu X...")
- Giải thích rõ ràng, dễ hiểu cho sinh viên
- Nếu câu hỏi không rõ ràng, hãy yêu cầu làm rõ

TÀI LIỆU THAM KHẢO:
{context_str}

CÂU HỎI: {question}

TRẢ LỜI:"""
        
        return prompt
    
    def generate_answer(
        self,
        question: str,
        contexts: List[Dict[str, Any]],
        temperature: float = None,
        max_tokens: int = None
    ) -> tuple[str, int]:
        """
        Generate câu trả lời từ LLM using Chat API
        
        Args:
            question: Câu hỏi gốc
            contexts: Danh sách contexts từ RAG
            temperature: Temperature (0-1)
            max_tokens: Max tokens
        
        Returns:
            tuple: (answer, tokens_used)
        """
        try:
            temperature = temperature or settings.LLM_TEMPERATURE
            max_tokens = max_tokens or settings.LLM_MAX_TOKENS
            
            # Build system message with contexts
            system_message = """Bạn là trợ lý học tập thông minh, giúp sinh viên trả lời câu hỏi dựa trên tài liệu học tập.

NGUYÊN TẮC:
- Trả lời dựa CHÍNH XÁC vào nội dung tài liệu được cung cấp bên dưới
- Nếu không tìm thấy thông tin trong tài liệu, hãy nói rõ "Tôi không tìm thấy thông tin này trong tài liệu"
- Trích dẫn nguồn khi trả lời (ví dụ: "Theo tài liệu...")
- Giải thích rõ ràng, dễ hiểu cho sinh viên
- Trả lời bằng tiếng Việt nếu câu hỏi bằng tiếng Việt

TÀI LIỆU THAM KHẢO:
"""
            
            # Add contexts to system message
            for idx, ctx in enumerate(contexts, 1):
                title = ctx.get("title", ctx.get("file_name", "Document"))
                system_message += f"\n[TÀI LIỆU {idx}] - {title}\n{ctx['chunk_text']}\n"
            
            # Build full message
            full_message = f"{system_message}\n\nCÂU HỎI: {question}\n\nTRẢ LỜI:"
            
            # Call Chat API
            response = self.cohere_client.chat(
                model=self.llm_model,
                message=full_message,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            answer = response.text.strip()
            
            # Get token usage if available
            tokens_used = 0
            if hasattr(response, 'meta') and response.meta and hasattr(response.meta, 'tokens'):
                tokens_info = response.meta.tokens
                if hasattr(tokens_info, 'input_tokens') and hasattr(tokens_info, 'output_tokens'):
                    tokens_used = tokens_info.input_tokens + tokens_info.output_tokens
                else:
                    tokens_used = len(full_message.split()) + len(answer.split())
            else:
                # Estimate if not available
                tokens_used = len(full_message.split()) + len(answer.split())
            
            return answer, tokens_used
        
        except Exception as e:
            raise Exception(f"LLM generation error: {e}")
    
    def query(
        self,
        question: str,
        user_id: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = None,
        score_threshold: float = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> Dict[str, Any]:
        """
        RAG query pipeline hoàn chỉnh
        
        Args:
            question: Câu hỏi
            user_id: User ID
            document_ids: Optional document IDs filter
            top_k: Số contexts
            score_threshold: Score threshold
            temperature: LLM temperature
            max_tokens: Max tokens
        
        Returns:
            Dict với answer, contexts, metadata
        """
        start_time = time.time()
        
        try:
            # Use defaults if not provided
            top_k = top_k or settings.RAG_TOP_K
            score_threshold = score_threshold or settings.RAG_SCORE_THRESHOLD
            
            # 1. Search relevant contexts
            contexts = self.search_relevant_contexts(
                query=question,
                user_id=user_id,
                document_ids=document_ids,
                top_k=top_k,
                score_threshold=score_threshold
            )
            
            if not contexts:
                return {
                    "answer": "Tôi không tìm thấy tài liệu phù hợp để trả lời câu hỏi này. Vui lòng upload thêm tài liệu hoặc thử câu hỏi khác.",
                    "contexts": [],
                    "model": self.llm_model,
                    "tokens_used": 0,
                    "processing_time": time.time() - start_time
                }
            
            # 2. Generate answer (Chat API)
            answer, tokens_used = self.generate_answer(
                question=question,
                contexts=contexts,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            processing_time = time.time() - start_time
            
            return {
                "answer": answer,
                "contexts": contexts,
                "model": self.llm_model,
                "tokens_used": tokens_used,
                "processing_time": processing_time
            }
        
        except Exception as e:
            raise Exception(f"RAG query error: {e}")
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        user_id: str,
        document_ids: Optional[List[str]] = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> Dict[str, Any]:
        """
        Chat với context từ documents
        
        Args:
            messages: Chat history [{"role": "user", "content": "..."}]
            user_id: User ID
            document_ids: Optional document IDs
            temperature: Temperature
            max_tokens: Max tokens
        
        Returns:
            Dict với response và metadata
        """
        try:
            # Get last user message
            last_message = messages[-1]["content"]
            
            # Search contexts based on last message
            contexts = self.search_relevant_contexts(
                query=last_message,
                user_id=user_id,
                document_ids=document_ids,
                top_k=3,  # Fewer contexts for chat
                score_threshold=0.75
            )
            
            # Build chat prompt with context
            if contexts:
                context_str = "\n\n".join([
                    f"[{ctx['file_name']}]: {ctx['chunk_text']}"
                    for ctx in contexts
                ])
                
                system_message = f"""Bạn là trợ lý học tập. Dựa vào tài liệu sau để trả lời:

{context_str}

Trả lời ngắn gọn, chính xác dựa trên tài liệu."""
            else:
                system_message = "Bạn là trợ lý học tập thông minh."
            
            # Build chat messages
            chat_messages = [{"role": "system", "content": system_message}]
            chat_messages.extend(messages)
            
            # Call Cohere chat API
            response = self.cohere_client.chat(
                message=last_message,
                chat_history=[
                    {"role": msg["role"], "message": msg["content"]}
                    for msg in messages[:-1]
                ] if len(messages) > 1 else None,
                preamble=system_message,
                model=self.llm_model,
                temperature=temperature or settings.LLM_TEMPERATURE,
                max_tokens=max_tokens or settings.LLM_MAX_TOKENS
            )
            
            return {
                "message": response.text,
                "contexts": contexts if contexts else None,
                "model": self.llm_model,
                "tokens_used": None  # Cohere chat doesn't return token count
            }
        
        except Exception as e:
            raise Exception(f"Chat error: {e}")


# Global instance
rag_service = RAGService()
