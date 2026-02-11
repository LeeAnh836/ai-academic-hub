"""
RAG Service
Retrieval Augmented Generation - Tìm kiếm context và generate câu trả lời

NOTE: This service is being deprecated in favor of the new Orchestrator.
Keeping for backward compatibility.
"""
from typing import List, Optional, Dict, Any
import time
import asyncio

from core.config import settings
from services.orchestrator import orchestrator


class RAGService:
    """Service xử lý RAG pipeline - now using Orchestrator"""
    
    def __init__(self):
        """Initialize with new Orchestrator"""
        self.orchestrator = orchestrator
        print("✅ RAGService initialized with Multi-Model Orchestrator")
    
    async def query_with_orchestrator(
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
        Query using new Multi-Model Orchestrator
        
        This is the NEW recommended method that supports:
        - Intent classification
        - Multi-model routing
        - Direct chat (no documents needed)
        - Smart fallback
        
        Args:
            question: User's question
            user_id: User ID
            document_ids: Optional document IDs
            top_k: Number of contexts
            score_threshold: Score threshold
            temperature: LLM temperature
            max_tokens: Max tokens
        
        Returns:
            Dict with answer, contexts, intent, model, etc.
        """
        try:
            # Use defaults if not provided
            top_k = top_k or settings.RAG_TOP_K
            score_threshold = score_threshold or settings.RAG_SCORE_THRESHOLD
            
            # Call orchestrator
            result = await self.orchestrator.process_query(
                question=question,
                user_id=user_id,
                document_ids=document_ids,
                top_k=top_k,
                score_threshold=score_threshold,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return result
        
        except Exception as e:
            raise Exception(f"Orchestrator query error: {e}")
    
    def classify_query_type(self, question: str) -> str:
        """
        Phân loại câu hỏi để áp dụng strategy phù hợp
        
        Returns:
            'factual': Hỏi thông tin cụ thể từ tài liệu
            'creative': Yêu cầu sáng tạo, tạo câu hỏi mới, brainstorm
            'analytical': Phân tích, so sánh, tổng hợp
        """
        question_lower = question.lower()
        
        # Creative indicators
        creative_keywords = [
            "đưa ra thêm câu hỏi", "tạo câu hỏi", "gợi ý câu hỏi",
            "câu hỏi khác", "câu hỏi tương tự", "brainstorm",
            "ý tưởng", "sáng tạo", "thêm câu hỏi"
        ]
        if any(kw in question_lower for kw in creative_keywords):
            return "creative"
        
        # Analytical indicators  
        analytical_keywords = [
            "so sánh", "khác nhau", "giống nhau", "phân tích",
            "tại sao", "làm thế nào", "tổng hợp", "đánh giá"
        ]
        if any(kw in question_lower for kw in analytical_keywords):
            return "analytical"
        
        # Default: factual
        return "factual"
    
    def search_relevant_contexts(
        self,
        query: str,
        user_id: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = 5,
        score_threshold: float = 0.5,
        enable_fallback: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm contexts liên quan từ Qdrant với fallback strategy
        
        Args:
            query: Câu hỏi/query
            user_id: User ID để filter
            document_ids: Optional list of document IDs để filter
            top_k: Số lượng kết quả
            score_threshold: Ngưỡng similarity score
            enable_fallback: Cho phép fallback nếu không đủ kết quả
        
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
            
            # FALLBACK STRATEGY: Nếu không đủ kết quả, giảm threshold
            if enable_fallback and len(search_results) < max(2, top_k // 2):
                min_threshold = settings.RAG_MIN_SCORE_THRESHOLD
                if score_threshold > min_threshold:
                    print(f"⚠️ Fallback: Giảm threshold từ {score_threshold} xuống {min_threshold}")
                    search_results = qdrant_manager.client.search(
                        collection_name=qdrant_manager.collection_name,
                        query_vector=query_vector,
                        query_filter=query_filter,
                        limit=top_k,
                        score_threshold=min_threshold
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
        query_type: str = "factual",
        temperature: float = None,
        max_tokens: int = None
    ) -> tuple[str, int]:
        """
        Generate câu trả lời từ LLM using Chat API với prompt phù hợp theo query type
        
        Args:
            question: Câu hỏi gốc
            contexts: Danh sách contexts từ RAG
            query_type: Loại câu hỏi (factual/creative/analytical)
            temperature: Temperature (0-1)
            max_tokens: Max tokens
        
        Returns:
            tuple: (answer, tokens_used)
        """
        try:
            temperature = temperature or settings.LLM_TEMPERATURE
            max_tokens = max_tokens or settings.LLM_MAX_TOKENS
            
            # Build context section
            context_section = "TÀI LIỆU THAM KHẢO:\n"
            for idx, ctx in enumerate(contexts, 1):
                title = ctx.get("title", ctx.get("file_name", "Document"))
                score = ctx.get("score", 0)
                context_section += f"\n[TÀI LIỆU {idx}] - {title} (độ liên quan: {score:.2f})\n{ctx['chunk_text']}\n"
            
            # Build system prompt based on query type
            if query_type == "creative":
                system_message = """Bạn là trợ lý học tập sáng tạo, giúp sinh viên mở rộng kiến thức.

NHIỆM VỤ:
- Dựa vào nội dung tài liệu để hiểu chủ đề và các khái niệm
- Sáng tạo câu hỏi mới, câu hỏi suy luận, câu hỏi mở rộng
- Câu hỏi phải liên quan đến kiến thức trong tài liệu nhưng có thể đi sâu hơn
- Đưa ra câu hỏi ở nhiều mức độ: dễ, trung bình, khó
- Giải thích ngắn gọn tại sao câu hỏi đó quan trọng

ĐỊNH DẠNG:
1. **Câu hỏi**: [câu hỏi]
   - **Mức độ**: [dễ/trung bình/khó]
   - **Lý do**: [tại sao câu hỏi này quan trọng]

"""
            elif query_type == "analytical":
                system_message = """Bạn là trợ lý phân tích thông minh, giúp sinh viên hiểu sâu về kiến thức.

NHIỆM VỤ:
- Phân tích, so sánh, đánh giá các khái niệm trong tài liệu
- Tìm ra mối liên hệ, điểm giống/khác, ưu/nhược điểm
- Giải thích bằng ví dụ cụ thể và dễ hiểu
- Có thể sử dụng kiến thức chung để làm rõ, nhưng phải dựa trên tài liệu

"""
            else:  # factual
                system_message = """Bạn là trợ lý học tập chính xác, giúp sinh viên tìm thông tin từ tài liệu.

NHIỆM VỤ:
- Trả lời dựa CHÍNH XÁC vào nội dung tài liệu được cung cấp
- Trích dẫn nguồn khi trả lời (ví dụ: "Theo tài liệu X...")
- Nếu không tìm thấy thông tin, nói rõ "Tôi không tìm thấy thông tin này trong tài liệu"
- Giải thích rõ ràng, dễ hiểu

"""
            
            # Build full message
            full_message = f"""{system_message}
{context_section}

CÂU HỎI: {question}

TRẢ LỜI:"""
            
            # Adjust temperature for creative queries
            if query_type == "creative":
                temperature = min(1.0, temperature + 0.2)  # Tăng creativity
            
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
        RAG query pipeline hoàn chỉnh với intelligent query processing
        
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
            # Classify query type
            query_type = self.classify_query_type(question)
            print(f"🔍 Query type detected: {query_type}")
            
            # Use defaults if not provided
            top_k = top_k or settings.RAG_TOP_K
            score_threshold = score_threshold or settings.RAG_SCORE_THRESHOLD
            
            # 1. Search relevant contexts with fallback
            contexts = self.search_relevant_contexts(
                query=question,
                user_id=user_id,
                document_ids=document_ids,
                top_k=top_k,
                score_threshold=score_threshold,
                enable_fallback=settings.RAG_ENABLE_FALLBACK
            )
            
            if not contexts:
                return {
                    "answer": "Tôi không tìm thấy tài liệu phù hợp để trả lời câu hỏi này. Vui lòng upload thêm tài liệu hoặc thử câu hỏi khác.",
                    "contexts": [],
                    "model": self.llm_model,
                    "tokens_used": 0,
                    "processing_time": time.time() - start_time,
                    "query_type": query_type
                }
            
            # Log contexts found
            scores_str = ", ".join([f"{c['score']:.2f}" for c in contexts[:3]])
            print(f"📚 Found {len(contexts)} contexts (scores: {scores_str})")
            
            # 2. Generate answer with appropriate prompt based on query type
            answer, tokens_used = self.generate_answer(
                question=question,
                contexts=contexts,
                query_type=query_type,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            processing_time = time.time() - start_time
            
            return {
                "answer": answer,
                "contexts": contexts,
                "model": self.llm_model,
                "tokens_used": tokens_used,
                "processing_time": processing_time,
                "query_type": query_type
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
