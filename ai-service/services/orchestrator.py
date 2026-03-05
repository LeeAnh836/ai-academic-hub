"""
AI Orchestrator - Multi-Model Query Processing
Main orchestrator that routes queries to appropriate handlers based on intent
"""
from typing import List, Dict, Optional, Any
import time

from core.config import settings
from core.model_manager import model_manager
from services.intent_classifier import intent_classifier
from services.embedding_service import embedding_service
from core.qdrant import qdrant_manager
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

# Import Hybrid RAG if GraphRAG is enabled
try:
    from services.hybrid_rag_service import hybrid_rag_service
    HYBRID_RAG_AVAILABLE = True
except ImportError:
    HYBRID_RAG_AVAILABLE = False


class AIOrchestrator:
    """
    Main orchestrator for AI queries
    Routes to appropriate handler based on intent classification
    """
    
    def __init__(self):
        """Initialize orchestrator"""
        self.model_manager = model_manager
        self.intent_classifier = intent_classifier
    
    async def process_query(
        self,
        question: str,
        user_id: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = 5,
        score_threshold: float = 0.5,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        session_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point - process query with intent classification
        
        Args:
            question: User's question
            user_id: User ID for filtering
            document_ids: Optional document IDs
            top_k: Number of contexts to retrieve
            score_threshold: Similarity threshold
            temperature: LLM temperature
            max_tokens: Max tokens
            session_history: Chat history
        
        Returns:
            Dict with answer, contexts, intent, model, etc.
        """
        start_time = time.time()
        
        try:
            # 1. Classify intent
            has_docs = bool(document_ids and len(document_ids) > 0)
            intent = self.intent_classifier.classify(
                question=question,
                has_documents=has_docs,
                document_count=len(document_ids) if document_ids else 0
            )
            
            print(f"🎯 Intent: {intent} | Has docs: {has_docs} | Question: {question[:50]}...")
            
            # 2. Route to appropriate handler
            if intent == "direct_chat" or intent == "code_help":
                result = await self.handle_direct_chat(
                    question=question,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    session_history=session_history
                )
            
            elif intent == "rag_query":
                result = await self.handle_rag_query(
                    question=question,
                    user_id=user_id,
                    document_ids=document_ids,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            
            elif intent == "summarization":
                result = await self.handle_summarization(
                    user_id=user_id,
                    document_ids=document_ids,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            
            elif intent == "question_generation":
                result = await self.handle_question_generation(
                    question=question,
                    user_id=user_id,
                    document_ids=document_ids,
                    top_k=top_k,
                    temperature=temperature
                )
            
            elif intent == "homework_solver":
                result = await self.handle_homework(
                    question=question,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            
            else:
                # Fallback to direct chat
                result = await self.handle_direct_chat(question, temperature, max_tokens)
            
            # 3. Add metadata
            result["intent"] = intent
            result["processing_time"] = time.time() - start_time
            result["user_id"] = user_id
            
            print(f"✅ Completed in {result['processing_time']:.2f}s")
            
            return result
        
        except Exception as e:
            print(f"❌ Orchestrator error: {e}")
            raise Exception(f"Query processing failed: {e}")
    
    async def handle_direct_chat(
        self,
        question: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        session_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Direct chat without RAG - for general questions, homework, coding
        Uses: Gemini Flash (fast, FREE)
        """
        try:
            # Select model
            provider_name, model_object = self.model_manager.get_model(
                task_type="direct_chat",
                complexity="low"
            )
            
            # System instruction
            system_instruction = """Bạn là trợ lý học tập thông minh, giúp sinh viên học tập hiệu quả.

CẤU TRÚC TRẢ LỜI BẮT BUỘC:

1. **TỔNG QUAN** (2-3 câu giới thiệu)

2. **CÁC KHÁI NIỆM CHÍNH** (Liệt kê ĐẦY ĐỦ TẤT CẢ trước khi giải thích)
   - Đánh số rõ ràng: 1, 2, 3, 4...
   - VD: "4 trụ cột OOP: 1) Encapsulation 2) Inheritance 3) Polymorphism 4) Abstraction"

3. **GIẢI THÍCH CHI TIẾT**
   - Giải thích TỪNG ĐIỂM đã liệt kê ở trên
   - Kèm ví dụ minh họa đơn giản
   - Không bỏ sót bất kỳ điểm nào

4. **ỨNG DỤNG THỰC TẾ** (nếu có)


5. **GỢI Ý TÌM HIỂU THÊM**
   - Đưa ra 2-3 câu hỏi cụ thể để học sâu hơn
   - VD: "💡 Muốn tìm hiểu thêm? Hãy hỏi: ..."

YÊU CẦU QUAN TRỌNG:
✅ Phải liệt kê ĐẦY ĐỦ tất cả điểm chính TRƯỚC KHI giải thích
✅ Không được bỏ sót bất kỳ khái niệm quan trọng nào
✅ Cân bằng giữa tổng quan và chi tiết
✅ Trả lời bằng tiếng Việt, thân thiện"""
            
            # Generate answer
            answer = self.model_manager.generate_text(
                provider_name=provider_name,
                model_identifier=model_object,
                prompt=question,
                system_instruction=system_instruction,
                temperature=temperature or 0.7,
                max_tokens=max_tokens or 4096  # Increased for comprehensive answers
            )
            
            return {
                "answer": answer,
                "contexts": [],
                "model": provider_name,
                "tokens_used": self._estimate_tokens(question, answer)
            }
        
        except Exception as e:
            # Fallback to Groq if Gemini fails
            print(f"⚠️ Primary model failed, trying fallback: {e}")
            return await self._fallback_chat(question, temperature, max_tokens)
    
    async def handle_rag_query(
        self,
        question: str,
        user_id: str,
        document_ids: Optional[List[str]],
        top_k: int = 5,
        score_threshold: float = 0.5,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        RAG query with document context
        Uses: Gemini Flash for simple, Gemini Pro for complex
        """
        try:
            # 1. Retrieve contexts from Qdrant
            contexts = await self._retrieve_contexts(
                query=question,
                user_id=user_id,
                document_ids=document_ids,
                top_k=top_k,
                score_threshold=score_threshold
            )
            
            if not contexts:
                # SMART NO-CONTEXT MESSAGE
                if document_ids:
                    # User has documents but no match found
                    return {
                        "answer": "🔍 Tôi không tìm thấy thông tin phù hợp với câu hỏi của bạn trong tài liệu đã chỉ định.\n\n"
                                  "**Gợi ý:**\n"
                                  "- Thử diễn đạt câu hỏi khác đi\n"
                                  "- Hỏi về các chủ đề có trong tài liệu\n"
                                  "- Hoặc hỏi tôi trực tiếp nếu đây là câu hỏi chung không liên quan đến tài liệu",
                        "contexts": [],
                        "model": "none",
                        "tokens_used": 0
                    }
                else:
                    # No documents specified - guide user
                    return {
                        "answer": "📚 **Tôi cần tài liệu để trả lời câu hỏi này!**\n\n"
                                  "Có vẻ như bạn đang hỏi về một tài liệu cụ thể, nhưng tôi chưa thấy tài liệu nào.\n\n"
                                  "**Cách khắc phục:**\n"
                                  "1. Upload tài liệu lên hệ thống\n"
                                  "2. Đợi xử lý hoàn tất (icon ✓ xanh)\n"
                                  "3. Hỏi lại câu hỏi\n\n"
                                  "**Hoặc:** Nếu đây là câu hỏi chung (không liên quan đến tài liệu), bạn có thể hỏi trực tiếp mà không cần file!",
                        "contexts": [],
                        "model": "none",
                        "tokens_used": 0
                    }
            
            # Log contexts found
            scores_preview = ", ".join([f"{c['score']:.2f}" for c in contexts[:3]])
            print(f"📚 Retrieved {len(contexts)} contexts (scores: {scores_preview})")
            
            # 2. Determine complexity and select model
            is_complex = self.intent_classifier.is_complex_query(question)
            provider_name, model_object = self.model_manager.get_model(
                task_type="rag_query",
                complexity="high" if is_complex else "low"
            )
            
            # 3. Build RAG prompt
            context_str = "\n\n".join([
                f"[Tài liệu {i+1} - {ctx['file_name']}]\n{ctx['chunk_text']}"
                for i, ctx in enumerate(contexts)
            ])
            
            # System instruction
            system_instruction = """Bạn là trợ lý học tập thông minh. Trả lời câu hỏi dựa trên tài liệu được cung cấp.

CẤU TRÚC TRẢ LỜI:

1. **TÓM TẮT NGẮN GỌN** (2-3 câu)

2. **CÁC ĐIỂM CHÍNH** (Liệt kê ĐẦY ĐỦ TẤT CẢ)
   - Đánh số rõ ràng: 1, 2, 3, 4...
   - Liệt kê HẾT các khái niệm/điểm quan trọng

3. **GIẢI THÍCH CHI TIẾT**
   - Giải thích TỪNG ĐIỂM đã liệt kê
   - Trích dẫn nguồn: "Theo Tài liệu 1..."
   - Kèm ví dụ từ tài liệu

4. **GỢI Ý KHÁM PHÁ THÊM**
   - 2-3 câu hỏi liên quan để học sâu hơn

NGUYÊN TẮC:
✅ Dựa CHÍNH XÁC vào nội dung tài liệu
✅ Liệt kê ĐẦY ĐỦ trước khi giải thích chi tiết
✅ Không bỏ sót điểm quan trọng nào
✅ Nếu không có thông tin, nói rõ ràng"""
            
            # Build user prompt
            user_prompt = f"""TÀI LIỆU:
{context_str}

CÂU HỎI: {question}

TRẢ LỜI:"""
            
            # 4. Generate answer with fallback
            answer, used_model = self._generate_with_fallback(
                provider_name=provider_name,
                model_identifier=model_object,
                prompt=user_prompt,
                system_instruction=system_instruction,
                temperature=temperature or settings.LLM_TEMPERATURE,
                max_tokens=max_tokens or 7000  # Very high for detailed RAG answers
            )
            
            return {
                "answer": answer,
                "contexts": contexts,
                "model": used_model,
                "tokens_used": self._estimate_tokens(context_str + question, answer)
            }
        
        except Exception as e:
            print(f"❌ RAG query error: {e}")
            raise Exception(f"RAG processing failed: {e}")
    
    async def handle_summarization(
        self,
        user_id: str,
        document_ids: Optional[List[str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Summarize full document(s)
        Uses: Gemini Pro (2M context, good for long documents)
        """
        try:
            if not document_ids or len(document_ids) == 0:
                return {
                    "answer": "Vui lòng chọn tài liệu cần tóm tắt.",
                    "contexts": [],
                    "model": "none",
                    "tokens_used": 0
                }
            
            # Retrieve ALL chunks from document (not just top-k)
            contexts = await self._retrieve_full_document(
                user_id=user_id,
                document_ids=document_ids
            )
            
            if not contexts:
                return {
                    "answer": "Không tìm thấy nội dung tài liệu.",
                    "contexts": [],
                    "model": "none",
                    "tokens_used": 0
                }
            
            # Use Gemini Pro for long context
            provider_name, model_object = self.model_manager.get_model(
                task_type="summarization",
                complexity="high"
            )
            
            # Build full document text
            full_text = "\n\n".join([
                f"[Phần {i+1}]\n{ctx['chunk_text']}"
                for i, ctx in enumerate(contexts)
            ])
            
            # System instruction
            system_instruction = """Bạn là trợ lý tóm tắt chuyên nghiệp.

NHIỆM VỤ:
Tóm tắt nội dung chính của tài liệu theo cấu trúc:

1. TỔNG QUAN (2-3 câu)
2. CÁC ĐIỂM CHÍNH (bullet points)
3. KẾT LUẬN (1-2 câu)

Yêu cầu:
- Ngắn gọn, súc tích
- Nắm bắt ý chính
- Dễ hiểu, rõ ràng
- Bằng tiếng Việt"""
            
            # Build user prompt
            user_prompt = f"""TÀI LIỆU:
{full_text}

TÓM TẮT:"""
            
            # Generate summary with fallback
            answer, used_model = self._generate_with_fallback(
                provider_name=provider_name,
                model_identifier=model_object,
                prompt=user_prompt,
                system_instruction=system_instruction,
                temperature=temperature or 0.5,
                max_tokens=max_tokens or 6000  # High for detailed summaries
            )
            
            return {
                "answer": answer,
                "contexts": contexts[:10],  # Return sample contexts
                "model": used_model,
                "tokens_used": self._estimate_tokens(full_text, answer)
            }
        
        except Exception as e:
            print(f"❌ Summarization error: {e}")
            raise Exception(f"Summarization failed: {e}")
    
    async def handle_question_generation(
        self,
        question: str,
        user_id: str,
        document_ids: Optional[List[str]],
        top_k: int = 10,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Generate questions from document content
        Uses: Gemini Pro (creative mode)
        """
        try:
            # Retrieve contexts
            contexts = await self._retrieve_contexts(
                query=question,
                user_id=user_id,
                document_ids=document_ids,
                top_k=top_k,
                score_threshold=0.3  # Lower threshold to get more content
            )
            
            if not contexts:
                return {
                    "answer": "Không tìm thấy nội dung để tạo câu hỏi. Vui lòng upload tài liệu.",
                    "contexts": [],
                    "model": "none",
                    "tokens_used": 0
                }
            
            # Use Gemini Pro for creativity
            provider_name, model_object = self.model_manager.get_model(
                task_type="question_generation",
                complexity="high"
            )
            
            # Build context
            context_str = "\n\n".join([ctx['chunk_text'] for ctx in contexts])
            
            # System instruction
            system_instruction = """Bạn là chuyên gia tạo câu hỏi học tập.

NHIỆM VỤ:
Dựa vào kiến thức trong tài liệu được cung cấp, tạo các câu hỏi để giúp sinh viên học tập và ôn tập hiệu quả.

YÊU CẦU:
- Tạo ít nhất 5-10 câu hỏi
- Phân loại theo mức độ: DỄ / TRUNG BÌNH / KHÓ
- Câu hỏi phải liên quan trực tiếp đến nội dung tài liệu
- Đa dạng: trắc nghiệm, tự luận, phân tích, so sánh
- Mỗi câu hỏi kèm giải thích tại sao nó quan trọng

ĐỊNH DẠNG:
**Câu 1** (Dễ): [Câu hỏi]
- *Lý do*: [Tại sao câu hỏi này quan trọng]

**Câu 2** (Trung bình): [Câu hỏi]
- *Lý do*: [Tại sao câu hỏi này quan trọng]"""
            
            # Build user prompt
            user_prompt = f"""KIẾN THỨC TỪ TÀI LIỆU:
{context_str}

YÊU CẦU: {question}

CÁC CÂU HỎI:"""
            
            # Generate questions with fallback
            answer, used_model = self._generate_with_fallback(
                provider_name=provider_name,
                model_identifier=model_object,
                prompt=user_prompt,
                system_instruction=system_instruction,
                temperature=temperature or 0.9,
                max_tokens=6000  # High for many detailed questions
            )
            
            return {
                "answer": answer,
                "contexts": contexts,
                "model": used_model,
                "tokens_used": self._estimate_tokens(context_str + question, answer)
            }
        
        except Exception as e:
            print(f"❌ Question generation error: {e}")
            raise Exception(f"Question generation failed: {e}")
    
    async def handle_homework(
        self,
        question: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Homework solver with step-by-step explanation
        Uses: Gemini Pro (best reasoning in FREE tier)
        """
        try:
            # Use Pro for complex reasoning
            provider_name, model_object = self.model_manager.get_model(
                task_type="homework_solver",
                complexity="high"
            )
            
            # System instruction
            system_instruction = """Bạn là gia sư chuyên nghiệp, giúp học sinh hiểu sâu kiến thức.

CẤU TRÚC HƯỚNG DẪN:

1. **PHÂN TÍCH ĐỀ BÀI**
   - Xác định yêu cầu
   - Dữ liệu đã cho
   - Điều cần tìm

2. **CÁCH TIẾP CẬN**
   - Phương pháp giải
   - Liệt kê ĐẦY ĐỦ TẤT CẢ bước cần làm
   - Lý do chọn cách này

3. **LỜI GIẢI CHI TIẾT**
   - Từng bước cụ thể
   - Giải thích logic
   - Tính toán (nếu có)
   - Code mẫu (nếu cần)

4. **KẾT LUẬN & KIỂM TRA**
   - Đáp án cuối cùng
   - Kiểm tra lại
   - Bài học rút ra

5. **GỢI Ý NÂNG CAO**
   - 2-3 câu hỏi/bài tập tương tự để luyện thêm
   - VD: "💡 Thử thách: ..."

YÊU CẦU:
✅ Hướng dẫn ĐẦY ĐỦ, không bỏ bước nào
✅ Giải thích dễ hiểu
✅ Khuyến khích tư duy
✅ Bằng tiếng Việt"""
            
            # Build user prompt
            user_prompt = f"""BÀI TẬP:
{question}

HƯỚNG DẪN:"""
            
            # Generate homework solution with fallback
            answer, used_model = self._generate_with_fallback(
                provider_name=provider_name,
                model_identifier=model_object,
                prompt=user_prompt,
                system_instruction=system_instruction,
                temperature=temperature or 0.7,
                max_tokens=max_tokens or 7000  # Very high for step-by-step solutions
            )
            
            return {
                "answer": answer,
                "contexts": [],
                "model": used_model,
                "tokens_used": self._estimate_tokens(question, answer)
            }
        
        except Exception as e:
            print(f"❌ Homework solver error: {e}")
            raise Exception(f"Homework solving failed: {e}")
    
    # ============================================
    # Helper Methods
    # ============================================
    def _generate_with_fallback(
        self,
        provider_name: str,
        model_identifier: str,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 7000  # Very high default
    ) -> tuple[str, str]:
        """
        Generate text with automatic fallback to Groq on 429 errors.
        Returns: (answer, used_model_name)
        """
        try:
            answer = self.model_manager.generate_text(
                provider_name=provider_name,
                model_identifier=model_identifier,
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return answer, provider_name
        
        except Exception as gen_error:
            error_str = str(gen_error)
            
            # If rate limit (429), fallback to Groq
            if "429" in error_str or "Too Many Requests" in error_str:
                print(f"⚠️ {provider_name} rate limit reached, falling back to Groq...")
                
                # Get Groq model
                fallback_provider, fallback_model = self.model_manager.get_model(
                    task_type="general",
                    complexity="medium",
                    force_provider="groq"
                )
                
                # Retry with Groq
                answer = self.model_manager.generate_text(
                    provider_name=fallback_provider,
                    model_identifier=fallback_model,
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                used_model = f"{fallback_provider} (fallback from {provider_name})"
                print(f"✅ Fallback successful with {fallback_provider}")
                return answer, used_model
            else:
                # Other errors, re-raise
                raise
    
    async def _retrieve_contexts(
        self,
        query: str,
        user_id: str,
        document_ids: Optional[List[str]],
        top_k: int,
        score_threshold: float
    ) -> List[Dict[str, Any]]:
        """
        Retrieve contexts using Hybrid RAG (if enabled) or Vector RAG only
        
        Hybrid RAG combines:
        - Vector search (Qdrant): Semantic similarity
        - Graph search (Neo4j): Entity relationships
        """
        try:
            # Use Hybrid RAG if GraphRAG is enabled
            if HYBRID_RAG_AVAILABLE and settings.ENABLE_GRAPH_RAG:
                print("🔀 Using Hybrid RAG (Vector + Graph)")
                return await hybrid_rag_service.hybrid_retrieve(
                    query=query,
                    user_id=user_id,
                    document_ids=document_ids,
                    top_k=top_k,
                    score_threshold=score_threshold
                )
            
            # Fallback to Vector RAG only (original implementation)
            print("📊 Using Vector RAG only")
            
            # Generate query embedding
            query_vector = embedding_service.embed_query(query)
            
            # Build filter
            filter_conditions = [
                FieldCondition(key="user_id", match=MatchValue(value=user_id))
            ]
            
            if document_ids:
                filter_conditions.append(
                    FieldCondition(key="document_id", match=MatchAny(any=document_ids))
                )
            
            query_filter = Filter(must=filter_conditions)
            
            # Search
            search_results = qdrant_manager.client.search(
                collection_name=qdrant_manager.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=score_threshold
            )
            
            # Fallback with lower threshold
            if len(search_results) < max(2, top_k // 2) and settings.RAG_ENABLE_FALLBACK:
                min_threshold = settings.RAG_MIN_SCORE_THRESHOLD
                if score_threshold > min_threshold:
                    print(f"⚠️ Fallback: Lowering threshold {score_threshold} -> {min_threshold}")
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
                contexts.append({
                    "chunk_id": result.id,
                    "score": result.score,
                    "chunk_text": result.payload.get("chunk_text", ""),
                    "chunk_index": result.payload.get("chunk_index", 0),
                    "document_id": result.payload.get("document_id", ""),
                    "file_name": result.payload.get("file_name", ""),
                    "title": result.payload.get("title", ""),
                    "source": "vector"
                })
            
            return contexts
        
        except Exception as e:
            print(f"❌ Context retrieval error: {e}")
            return []
    
    async def _retrieve_full_document(
        self,
        user_id: str,
        document_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Retrieve all chunks from document(s) for summarization"""
        try:
            filter_conditions = [
                FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                FieldCondition(key="document_id", match=MatchAny(any=document_ids))
            ]
            
            query_filter = Filter(must=filter_conditions)
            
            # Scroll to get all chunks (not search)
            results, _ = qdrant_manager.client.scroll(
                collection_name=qdrant_manager.collection_name,
                scroll_filter=query_filter,
                limit=100,  # Max chunks per document
                with_payload=True,
                with_vectors=False
            )
            
            # Sort by chunk_index
            contexts = []
            for result in results:
                contexts.append({
                    "chunk_id": result.id,
                    "score": 1.0,  # No score for scroll
                    "chunk_text": result.payload.get("chunk_text", ""),
                    "chunk_index": result.payload.get("chunk_index", 0),
                    "document_id": result.payload.get("document_id", ""),
                    "file_name": result.payload.get("file_name", ""),
                    "title": result.payload.get("title", "")
                })
            
            # Sort by chunk index
            contexts.sort(key=lambda x: x["chunk_index"])
            
            return contexts
        
        except Exception as e:
            print(f"❌ Full document retrieval error: {e}")
            return []
    
    async def _fallback_chat(
        self,
        question: str,
        temperature: Optional[float],
        max_tokens: Optional[int]
    ) -> Dict[str, Any]:
        """Fallback to any available model"""
        try:
            # Try to get any model (will use fallback chain automatically)
            provider_name,model_object = self.model_manager.get_model(
                task_type="direct_chat",
                complexity="low"
            )
            
            # System instruction
            system_instruction = "Bạn là trợ lý thông minh. Trả lời câu hỏi của người dùng."
            
            # Generate answer
            answer = self.model_manager.generate_text(
                provider_name=provider_name,
                model_identifier=model_object,
                prompt=question,
                system_instruction=system_instruction,
                temperature=temperature or 0.7,
                max_tokens=max_tokens or 7000  # Very high for comprehensive answers
            )
            
            return {
                "answer": answer,
                "contexts": [],
                "model": f"{provider_name}-fallback",
                "tokens_used": self._estimate_tokens(question, answer)
            }
        
        except Exception as e:
            raise Exception(f"All models failed: {e}")
    

    
    def _estimate_tokens(self, input_text: str, output_text: str) -> int:
        """Rough token estimation"""
        return len(input_text.split()) + len(output_text.split())


# Global singleton instance
orchestrator = AIOrchestrator()
