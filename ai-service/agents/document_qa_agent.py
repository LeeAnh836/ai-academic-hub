"""
Document QA Agent
Handles question-answering from uploaded documents using RAG
"""
from typing import Dict, Any, List, Optional
import logging

from agents import BaseAgent
from services.embedding_service import embedding_service
from services.hybrid_rag_service import hybrid_rag_service
from services.advanced_rag_service import advanced_rag_service
from services.corrective_rag import corrective_rag
from core.qdrant import qdrant_manager
from core.config import settings
from services.query_complexity_analyzer import complexity_analyzer
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

logger = logging.getLogger(__name__)


class DocumentQAAgent(BaseAgent):
    """
    Agent for document-based question answering (RAG)
    """
    
    def __init__(self):
        super().__init__(
            agent_name="document_qa_agent",
            description="Answers questions from uploaded documents using RAG"
        )
    
    async def execute(
        self,
        query: str,
        user_id: str,
        session_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute document QA task
        
        Args:
            query: User question
            user_id: User ID
            session_id: Session ID
            context: Must contain:
                - document_ids: List of document IDs (optional)
                - top_k: Number of contexts to retrieve
                - score_threshold: Similarity threshold
        
        Returns:
            Dict with answer and sources
        """
        try:
            logger.info(f"📚 Document QA: {query}")
            
            # Get parameters
            document_ids = context.get("document_ids")
            top_k = context.get("top_k", settings.RAG_TOP_K)
            score_threshold = context.get("score_threshold", settings.RAG_SCORE_THRESHOLD)
            chat_history = context.get("chat_history", [])
            
            # Validate that documents are provided
            # If no document_ids provided, don't search all user documents
            if not document_ids or len(document_ids) == 0:
                logger.warning("⚠️ No document_ids provided for RAG query")
                return {
                    "answer": "📎 **Vui lòng chọn tài liệu bạn muốn hỏi**\n\nBạn chưa chọn tài liệu nào. Hãy:\n1. Upload tài liệu (nếu chưa có)\n2. Click vào biểu tượng 📎 ở ô nhập tin nhắn\n3. Chọn tài liệu bạn muốn hỏi\n\nSau đó hỏi lại câu hỏi của bạn!",
                    "contexts": [],
                    "metadata": {"no_documents_selected": True}
                }
            
            # Analyze query complexity (before retrieval so it can influence strategy)
            complexity = complexity_analyzer.analyze(query)
            logger.info(f"📊 Query complexity: {complexity}")
            
            # Retrieve relevant contexts
            contexts, pipeline_meta = await self._retrieve_contexts(
                query=query,
                user_id=user_id,
                document_ids=document_ids,
                top_k=top_k,
                score_threshold=score_threshold,
                complexity=complexity
            )
            
            if not contexts:
                return {
                    "answer": "Tôi không tìm thấy thông tin phù hợp trong tài liệu của bạn. Vui lòng thử câu hỏi khác hoặc upload thêm tài liệu.",
                    "contexts": [],
                    "metadata": {"no_context_found": True}
                }
            
            # Generate answer from contexts
            answer = await self._generate_answer(query, contexts, complexity, chat_history)
            
            # Save state
            self.save_state(user_id, session_id, {
                "last_query": query,
                "contexts_used": len(contexts)
            })
            
            self.memory.set_context(user_id, session_id, "last_action", "document_qa")
            
            # Determine retrieval mode label
            if settings.ENABLE_ADVANCED_RAG:
                retrieval_mode = "advanced_rag"
            elif settings.ENABLE_GRAPH_RAG:
                retrieval_mode = "hybrid"
            else:
                retrieval_mode = "vector_only"
            
            return {
                "answer": answer,
                "contexts": contexts,
                "metadata": {
                    "model": "gemini-flash",
                    "contexts_count": len(contexts),
                    "retrieval_mode": retrieval_mode,
                    "pipeline": pipeline_meta
                }
            }
        
        except Exception as e:
            logger.error(f"❌ Document QA error: {e}")
            return {
                "answer": f"Lỗi khi tra cứu tài liệu: {e}",
                "contexts": [],
                "metadata": {"error": str(e)}
            }
    
    async def _retrieve_contexts(
        self,
        query: str,
        user_id: str,
        document_ids: Optional[List[str]],
        top_k: int,
        score_threshold: float,
        complexity: str = "moderate"
    ) -> tuple:
        """
        Retrieve relevant contexts using the best available strategy:
        1. Advanced RAG (ENABLE_ADVANCED_RAG=True): Full pipeline with query expansion,
           BM25 rescoring, re-ranking, CRAG, and multi-hop reasoning
        2. Hybrid RAG (ENABLE_GRAPH_RAG=True): Vector + Graph (Neo4j) retrieval
        3. Vector-only: Direct Qdrant similarity search (fallback)

        Returns:
            Tuple of (contexts, pipeline_metadata)
        """
        # ── Advanced RAG path ────────────────────────────────────────────
        if settings.ENABLE_ADVANCED_RAG:
            try:
                use_multihop = corrective_rag.should_use_multi_hop(query, complexity)
                if use_multihop:
                    logger.info("🔀 Using multi-hop Advanced RAG")
                    contexts, meta = await advanced_rag_service.retrieve_with_multihop(
                        query=query,
                        user_id=user_id,
                        document_ids=document_ids,
                        top_k=top_k,
                        score_threshold=score_threshold
                    )
                else:
                    contexts, meta = await advanced_rag_service.retrieve(
                        query=query,
                        user_id=user_id,
                        document_ids=document_ids,
                        top_k=top_k,
                        score_threshold=score_threshold,
                        complexity=complexity
                    )
                logger.info(f"🚀 Advanced RAG retrieved {len(contexts)} contexts")
                return contexts, meta
            except Exception as e:
                logger.warning(f"⚠️ Advanced RAG failed, falling back: {e}")
                # Fall through to next strategy

        # ── Hybrid path (Qdrant + Neo4j) ────────────────────────────────
        if settings.ENABLE_GRAPH_RAG:
            try:
                contexts = await hybrid_rag_service.hybrid_retrieve(
                    query=query,
                    user_id=user_id,
                    document_ids=document_ids,
                    top_k=top_k,
                    score_threshold=score_threshold
                )
                logger.info(f"🔀 Hybrid RAG retrieved {len(contexts)} contexts")
                return contexts, {"pipeline": "hybrid_rag"}
            except Exception as e:
                logger.warning(f"⚠️ Hybrid RAG failed, falling back to vector-only: {e}")
                # Fall through to vector-only path below

        # ── Vector-only path (Qdrant direct) ────────────────────────────
        try:
            query_vector = embedding_service.embed_query(query)

            filter_conditions = [
                FieldCondition(key="user_id", match=MatchValue(value=user_id))
            ]

            if document_ids and len(document_ids) > 0:
                filter_conditions.append(
                    FieldCondition(key="document_id", match=MatchAny(any=document_ids))
                )
                logger.info(f"🔍 Vector search in {len(document_ids)} specific documents")
            else:
                logger.warning("⚠️ No document_ids provided - returning empty contexts")
                return [], {"pipeline": "vector_only"}

            query_filter = Filter(must=filter_conditions)

            search_results = qdrant_manager.client.search(
                collection_name=qdrant_manager.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=score_threshold
            )

            # Fallback with lower threshold if not enough results
            if len(search_results) < max(2, top_k // 2) and settings.RAG_ENABLE_FALLBACK:
                min_threshold = settings.RAG_MIN_SCORE_THRESHOLD
                if score_threshold > min_threshold:
                    logger.info(f"⚠️ Lowering threshold {score_threshold} → {min_threshold}")
                    search_results = qdrant_manager.client.search(
                        collection_name=qdrant_manager.collection_name,
                        query_vector=query_vector,
                        query_filter=query_filter,
                        limit=top_k,
                        score_threshold=min_threshold
                    )

            contexts = []
            for result in search_results:
                contexts.append({
                    "chunk_id": result.id,
                    "score": result.score,
                    "chunk_text": result.payload.get("chunk_text", ""),
                    "chunk_index": result.payload.get("chunk_index", 0),
                    "document_id": result.payload.get("document_id", ""),
                    "file_name": result.payload.get("file_name", ""),
                    "title": result.payload.get("title", "")
                })

            logger.info(f"📚 Vector-only retrieved {len(contexts)} contexts")
            return contexts, {"pipeline": "vector_only"}
        
        except Exception as e:
            logger.error(f"❌ Context retrieval error: {e}")
            return [], {"pipeline": "error", "error": str(e)}
    
    async def _generate_answer(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        complexity: str = "moderate",
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Generate answer from contexts using LLM
        
        Args:
            query: User query
            contexts: Retrieved contexts
            complexity: Query complexity level
            chat_history: Recent conversation turns for follow-up context
        """
        try:
            # Build context string
            context_str = "\n\n".join([
                f"[Tài liệu {i+1} - {ctx['file_name']}]\n{ctx['chunk_text']}"
                for i, ctx in enumerate(contexts)
            ])
            
            # Build chat history section (last 6 messages = 3 turns)
            history_section = ""
            if chat_history:
                recent = chat_history[-6:]
                lines = []
                for msg in recent:
                    role_label = "Người dùng" if msg.get("role") == "user" else "Trợ lý"
                    lines.append(f"{role_label}: {msg.get('content', '')}")
                history_section = "\nLỊCH SỬ TRÒ CHUYỆN GẦN ĐÂY:\n" + "\n".join(lines) + "\n"
            
            # Detect request type: creative vs analytical
            request_type = self._detect_request_type(query)
            
            # Dynamic system instruction based on complexity and type
            system_instruction = self._get_system_prompt_rag(complexity, request_type)
            
            # Build prompt
            user_prompt = f"""TÀI LIỆU:
{context_str}
{history_section}
CÂU HỎI: {query}

TRẢ LỜI:"""
            
            # Map complexity to model selection
            model_complexity = {
                "simple": "low",
                "moderate": "medium",
                "complex": "high"
            }.get(complexity, "medium")
            
            # Get appropriate model
            provider_name, model_identifier = self.model_manager.get_model(
                task_type="rag_query",
                complexity=model_complexity
            )
            
            # Lower temperature for RAG (need accuracy from documents)
            temperature = 0.2 if complexity in ["moderate", "complex"] else 0.5
            
            print(f"🤖 RAG using {provider_name} | model: {model_identifier} | complexity: {complexity} | temp: {temperature}")
            
            answer = self.model_manager.generate_text(
                provider_name=provider_name,
                model_identifier=model_identifier,
                prompt=user_prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=4000
            )
            
            return answer
        
        except Exception as e:
            logger.error(f"❌ Answer generation error: {e}")
            return f"Lỗi khi tạo câu trả lời: {e}"
    
    def _detect_request_type(self, query: str) -> str:
        """
        Detect if query is creative (writing) or analytical (Q&A)
        
        Returns:
            "creative" or "analytical"
        """
        query_lower = query.lower()
        
        # Creative keywords
        creative_keywords = [
            "viết", "write", "tạo ra", "create", "compose",
            "draft", "soạn", "sáng tác", "làm thơ", "làm bài",
            "vẽ", "thiết kế", "design", "kể chuyện", "story",
            "tóm tắt thành", "viết lại", "viết thành", "chuyển thành"
        ]
        
        return "creative" if any(kw in query_lower for kw in creative_keywords) else "analytical"
    
    def _get_system_prompt_rag(self, complexity: str, request_type: str = "analytical") -> str:
        """
        Get dynamic RAG system prompt based on complexity and request type
        
        Args:
            complexity: "simple" | "moderate" | "complex"
            request_type: "creative" | "analytical"
        
        Returns:
            System instruction for RAG
        """
        if complexity == "simple":
            return """Bạn là trợ lý học tập. Trả lời NGẮN GỌN dựa trên tài liệu.

YÊU CẦU:
✅ Trả lời TRỰC TIẾP từ tài liệu
✅ Chỉ 1-2 câu
✅ Trích dẫn: "Theo tài liệu, ..."
✅ KHÔNG giải thích dài dòng
✅ KHÔNG dùng heading/format phức tạp

VÍ DỤ:
- "Định nghĩa X?" → "Theo tài liệu, X là..."
- "Công thức Y?" → "Y = ..."
"""
        
        elif complexity == "moderate":
            # CREATIVE MODE: Viết dựa trên tài liệu
            if request_type == "creative":
                return """Bạn là trợ lý sáng tạo nội dung. Sử dụng tài liệu làm nguồn để thực hiện yêu cầu.

NGUYÊN TẮC:
✅ **DỰA VÀO TÀI LIỆU**: Sử dụng thông tin từ tài liệu làm nguồn chính
✅ **TỰ NHIÊN**: Viết thành đoạn văn/bài viết tự nhiên, KHÔNG dùng format cứng nhắc
✅ **PHÙHỢP YÊU CẦU**: Tuân thủ độ dài, phong cách người dùng yêu cầu
✅ **SÁNG TẠO**: Tổ chức nội dung từ tài liệu một cách mạch lạc, hấp dẫn

YÊU CẦU:
✅ KHÔNG dùng format "Định nghĩa/Các thành phần/Giải thích"
✅ KHÔNG dùng heading/bullet points trừ khi người dùng yêu cầu
✅ Viết thành đoạn văn liền mạch, tự nhiên
✅ Tuân thủ độ dài người dùng yêu cầu (nếu có)
✅ Trích dẫn tự nhiên: "Theo tài liệu,... " hoặc tích hợp vào câu văn
✅ Kết thúc hoàn chỉnh, không dang dở

VÍ DỤ:
YC: "Viết đoạn văn 200 chữ về bảo vệ môi trường từ tài liệu"
TL: "Bảo vệ môi trường là trách nhiệm của mỗi người... [đoạn văn tự nhiên dựa trên tài liệu]..."

❌ KHÔNG TRẢ LỜI KIỂU:
"Định nghĩa/Tóm tắt: ...
Các thành phần chính:
- Điểm 1
- Điểm 2"
"""
            
            # ANALYTICAL MODE: Trả lời câu hỏi từ tài liệu
            else:
                return """Bạn là trợ lý học tập chuyên môn. Trả lời CHÍNH XÁC và ĐẦY ĐỦ dựa trên tài liệu.

NGUYÊN TẮC:
✅ **CHÍNH XÁC tuyệt đối**: Chỉ dựa vào tài liệu cung cấp
✅ **ĐẦY ĐỦ**: Không bỏ sót thông tin quan trọng từ tài liệu
✅ **TRÍCH DẪN RÕ RÀNG**: Ghi rõ nguồn "Theo Tài liệu X, ..."
✅ **CÓ CẤU TRÚC**: Dùng markdown để dễ đọc

FORMAT OUTPUT: Markdown (dùng **, -)

CẤU TRÚC:
- **Định nghĩa/Tóm tắt**: 1-2 câu ngắn gọn
- **Các thành phần/khía cạnh chính**: Liệt kê ĐẦY ĐỦ từ tài liệu
- **Giải thích**: Mỗi thành phần 1-2 câu
- **Trích dẫn**: "Theo Tài liệu X, ..."

YÊU CẦU:
✅ Dựa HOÀN TOÀN vào tài liệu
✅ Không thêm kiến thức bên ngoài
✅ Không quá 250 từ
✅ Dùng markdown: **bold**, - bullet
✅ CẤM bỏ sót thông tin quan trọng trong tài liệu

VÍ DỤ TRẢ LỜI TỐT:
"Theo tài liệu, OOP có **4 nguyên lý cơ bản**: **Encapsulation** (đóng gói), **Inheritance** (kế thừa), **Polymorphism** (đa hình), và **Abstraction** (trừu tượng hóa)..."
"""
        
        else:  # complex
            # CREATIVE MODE: Viết nội dung phức tạp từ tài liệu
            if request_type == "creative":
                return """Bạn là chuyên gia sáng tạo nội dung chuyên nghiệp. Sử dụng tài liệu để tạo nội dung chất lượng cao.

NGUYÊN TẮC:
✅ **DỰA VÀO TÀI LIỆU**: Sử dụng tài liệu làm nguồn chính, đầy đủ
✅ **CHUYÊN NGHIỆP**: Nội dung có chiều sâu, chất lượng
✅ **TỰ NHIÊN**: Viết mạch lạc, lưu loát như người viết
✅ **PHÙ HỢP YÊU CẦU**: Tuân thủ độ dài, phong cách, cấu trúc
✅ **HOÀN CHỈNH**: Có mở bài, thân bài, kết luận (nếu phù hợp)

YÊU CẦU:
✅ KHÔNG dùng format cứng nhắc "Định nghĩa/Thành phần/Giải thích"
✅ Tự nhiên, lưu loát như văn bản do người viết
✅ Có thể dùng heading ### nếu yêu cầu viết bài dài, có cấu trúc
✅ Tuân thủ độ dài yêu cầu
✅ Trích dẫn tự nhiên: "Theo tài liệu,..." tích hợp vào nội dung

VÍ DỤ:
YC: "Viết bài phân tích dựa trên tài liệu"
TL: Viết thành bài phân tích hoàn chỉnh, có cấu trúc, dựa 100% vào tài liệu
"""
            
            # ANALYTICAL MODE: Phân tích chuyên sâu từ tài liệu
            else:
                return """Bạn là trợ lý học tập chuyên sâu. Trả lời CHI TIẾT và TOÀN DIỆN dựa trên tài liệu.

NGUYÊN TẮC:
✅ **CHÍNH XÁC tuyệt đối**: Chỉ dựa vào tài liệu cung cấp
✅ **ĐẦY ĐỦ**: Bao gồm TẤT CẢ thông tin quan trọng từ tài liệu
✅ **CÓ CHIỀU SÂU**: Phân tích kỹ lưỡng, kết nối các ý
✅ **TRÍCH DẪN cụ thể**: Ghi rõ "Theo Tài liệu X, ..."
✅ **CÓ CẤU TRÚC**: Markdown với heading và formatting

FORMAT OUTPUT: Markdown (dùng ###, **, -, 1.)

CẤU TRÚC TRẢ LỜI:

### 1. Tóm Tắt
2-3 câu tóm tắt ngắn gọn từ tài liệu

### 2. Các Điểm Chính
Liệt kê **ĐẦY ĐỦ TẤT CẢ** các điểm quan trọng từ tài liệu:
1. **Điểm 1**: Mô tả chi tiết
   - Trích dẫn: "Theo Tài liệu X, ..."
2. **Điểm 2**: Mô tả chi tiết
   - Trích dẫn: "Theo Tài liệu X, ..."
(Tiếp tục cho đến hết)

### 3. Giải Thích Chi Tiết
- Phân tích TỪNG ĐIỂM đã liệt kê
- Làm rõ mối liên hệ giữa các điểm
- Kèm ví dụ cụ thể từ tài liệu
- Trích dẫn rõ ràng: "**Theo Tài liệu 1**, ..."

### 4. Kết Luận và Gợi Ý
- Tóm lại các điểm chính
- Gợi ý câu hỏi liên quan để tìm hiểu thêm

YÊU CẦU:
✅ Dựa HOÀN TOÀN vào tài liệu (không tự thêm kiến thức)
✅ Chi tiết (~400-600 từ)
✅ CẤM bỏ sót thông tin quan trọng
✅ Trích dẫn cụ thể từng phần
"""


# Global singleton
document_qa_agent = DocumentQAAgent()
