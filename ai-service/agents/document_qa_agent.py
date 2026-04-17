"""
Document QA Agent
Handles question-answering from uploaded documents using RAG
"""
from typing import Dict, Any, List, Optional
from collections import OrderedDict
import logging
import re

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
            top_k = int(context.get("top_k") or settings.RAG_TOP_K)
            score_threshold = float(context.get("score_threshold") or settings.RAG_SCORE_THRESHOLD)
            chat_history = context.get("chat_history", [])
            conversation_summary = context.get("conversation_summary")
            source_metadata = context.get("source_metadata", [])
            intent = context.get("intent", "")
            
            # Validate that documents are provided
            # If no document_ids provided, don't search all user documents
            if not document_ids or len(document_ids) == 0:
                logger.warning("⚠️ No document_ids provided for RAG query")
                return {
                    "answer": "📎 **Vui lòng chọn tài liệu bạn muốn hỏi**\n\nBạn chưa chọn tài liệu nào. Hãy:\n1. Upload tài liệu (nếu chưa có)\n2. Click vào biểu tượng 📎 ở ô nhập tin nhắn\n3. Chọn tài liệu bạn muốn hỏi\n\nSau đó hỏi lại câu hỏi của bạn!",
                    "contexts": [],
                    "metadata": {"no_documents_selected": True}
                }
            
            # ── Summarization path ─────────────────────────────────────
            # If intent is summarization, use dedicated pipeline that
            # scrolls ALL chunks from ALL documents instead of semantic
            # search (which biases towards only one document).
            if intent == "summarization" or self._is_summarization_query(query):
                logger.info("📝 Summarization detected → full-document pipeline")
                return await self._execute_summarization(
                    query=query,
                    user_id=user_id,
                    session_id=session_id,
                    document_ids=document_ids,
                    chat_history=chat_history,
                )
            
            # ── Normal RAG path ────────────────────────────────────────
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

            # Reference-query fallback:
            # For prompts like "giai bai nay" / "this image", semantic search
            # can miss because the query itself is generic. In that case, pull
            # leading chunks directly from selected documents.
            if not contexts and self._is_reference_query(query):
                logger.info(
                    "🔁 No semantic contexts; trying reference-aware "
                    "document fallback retrieval"
                )
                fallback_contexts = await self._retrieve_reference_contexts(
                    user_id=user_id,
                    document_ids=document_ids,
                    top_k=max(3, top_k),
                )
                pipeline_meta["reference_fallback"] = {
                    "used": bool(fallback_contexts),
                    "contexts_count": len(fallback_contexts),
                }
                if fallback_contexts:
                    contexts = fallback_contexts
            
            if not contexts:
                return {
                    "answer": "Tôi không tìm thấy thông tin phù hợp trong tài liệu của bạn. Vui lòng thử câu hỏi khác hoặc upload thêm tài liệu.",
                    "contexts": [],
                    "metadata": {"no_context_found": True}
                }
            
            # Generate answer from contexts
            answer = await self._generate_answer(
                query=query,
                contexts=contexts,
                complexity=complexity,
                chat_history=chat_history,
                conversation_summary=conversation_summary,
                source_metadata=source_metadata,
            )
            
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
            
            # Build doc_map for frontend clickable links
            doc_map = self._build_doc_map(contexts)
            
            return {
                "answer": answer,
                "contexts": contexts,
                "metadata": {
                    "model": "gemini-flash",
                    "contexts_count": len(contexts),
                    "retrieval_mode": retrieval_mode,
                    "pipeline": pipeline_meta,
                    "doc_map": doc_map,
                    **self.build_quota_metadata(answer)
                }
            }
        
        except Exception as e:
            logger.error(f"❌ Document QA error: {e}")
            err_text = f"Lỗi khi tra cứu tài liệu: {e}"
            return {
                "answer": err_text,
                "contexts": [],
                "metadata": {
                    "error": str(e),
                    **self.build_quota_metadata(err_text)
                }
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

    def _is_reference_query(self, query: str) -> bool:
        """
        Detect deictic queries that usually refer to attached files/images,
        e.g. "giai bai nay", "lam cau nay", "this image".
        """
        query_lower = (query or "").lower().strip()
        if not query_lower:
            return False

        explicit_markers = [
            "file này", "file nay", "tài liệu này", "tai lieu nay",
            "ảnh này", "anh nay", "hình này", "hinh nay",
            "this file", "this document", "this image", "attached file",
        ]
        if any(marker in query_lower for marker in explicit_markers):
            return True

        deictic_markers = [
            "này", "nay", "đó", "do", "kia",
            "this", "that", "above", "attached",
        ]
        object_markers = [
            "bài", "bai", "bài tập", "bai tap", "đề", "de", "câu", "cau",
            "hình", "hinh", "ảnh", "anh", "file", "tài liệu", "tai lieu",
            "problem", "exercise", "question", "image", "document",
        ]

        has_deictic = any(marker in query_lower for marker in deictic_markers)
        has_object = any(marker in query_lower for marker in object_markers)

        return has_deictic and has_object and len(query_lower.split()) <= 18

    async def _retrieve_reference_contexts(
        self,
        user_id: str,
        document_ids: List[str],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """
        Pull leading chunks directly from selected documents (scroll-based)
        when semantic retrieval returns nothing for generic reference queries.
        """
        try:
            per_doc_collections: List[List[Dict[str, Any]]] = []
            per_doc_limit = max(4, min(20, top_k + 2))

            for doc_id in document_ids:
                query_filter = Filter(
                    must=[
                        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                        FieldCondition(key="document_id", match=MatchValue(value=doc_id)),
                    ]
                )

                results, _ = qdrant_manager.client.scroll(
                    collection_name=qdrant_manager.collection_name,
                    scroll_filter=query_filter,
                    limit=per_doc_limit,
                    with_payload=True,
                    with_vectors=False,
                )

                doc_contexts: List[Dict[str, Any]] = []
                for result in results:
                    chunk_text = result.payload.get("chunk_text", "")
                    if not chunk_text:
                        continue
                    doc_contexts.append({
                        "chunk_id": result.id,
                        "score": 1.0,
                        "chunk_text": chunk_text,
                        "chunk_index": result.payload.get("chunk_index", 0),
                        "document_id": result.payload.get("document_id", ""),
                        "file_name": result.payload.get("file_name", ""),
                        "title": result.payload.get("title", ""),
                        "source": "reference_fallback",
                    })

                doc_contexts.sort(key=lambda item: item.get("chunk_index", 0))
                if doc_contexts:
                    per_doc_collections.append(doc_contexts)

            if not per_doc_collections:
                return []

            selected: List[Dict[str, Any]] = []
            remainder: List[Dict[str, Any]] = []

            # First pass: take first chunk from each document
            for doc_contexts in per_doc_collections:
                selected.append(doc_contexts[0])
                remainder.extend(doc_contexts[1:])

            # Second pass: fill remaining slots from subsequent chunks
            if len(selected) < top_k:
                selected.extend(remainder[: top_k - len(selected)])

            return selected[:top_k]

        except Exception as e:
            logger.warning(f"⚠️ Reference fallback retrieval failed: {e}")
            return []
    
    async def _generate_answer(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        complexity: str = "moderate",
        chat_history: Optional[List[Dict[str, Any]]] = None,
        conversation_summary: Optional[str] = None,
        source_metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Generate answer from contexts using LLM.
        Routes to Map-Reduce pipeline for multi-document queries.
        
        Args:
            query: User query
            contexts: Retrieved contexts
            complexity: Query complexity level
            chat_history: Recent conversation turns for follow-up context
        """
        try:
            # Check if this is a multi-document query requiring Map-Reduce
            if self._is_multi_document_query(query, contexts):
                logger.info("📑 Multi-document query detected → Map-Reduce pipeline")
                return await self._generate_map_reduce_answer(
                    query, contexts, complexity, chat_history
                )

            # Group contexts by document for better LLM comprehension
            grouped = self._group_contexts_by_document(contexts)
            if len(grouped) > 1:
                # Multiple documents but not a multi-doc-specific query:
                # still group contexts for clarity
                context_str = self._build_grouped_context_str(grouped)
            else:
                context_str = "\n\n".join([
                    f"[{self._build_source_label(ctx)}]\n{ctx['chunk_text']}"
                    for i, ctx in enumerate(contexts)
                ])
            
            # Build chat history section (last 12 messages = 6 turns)
            history_section = self._build_history_section(chat_history)
            summary_section = self._build_summary_section(conversation_summary)
            source_meta_section = self._build_source_metadata_section(source_metadata)
            
            # Detect request type: creative vs analytical
            request_type = self._detect_request_type(query)
            
            # Dynamic system instruction based on complexity and type
            system_instruction = self._get_system_prompt_rag(complexity, request_type)
            
            # Build prompt with explicit grounding instruction
            user_prompt = f"""=== BẮT ĐẦU TÀI LIỆU (CHỈ sử dụng thông tin trong phần này) ===
{context_str}
=== KẾT THÚC TÀI LIỆU ===
{summary_section}
{source_meta_section}
{history_section}
CÂU HỎI: {query}

⚠️ NHẮC LẠI: Chỉ trả lời dựa trên NỘI DUNG TÀI LIỆU ở trên. KHÔNG thêm kiến thức bên ngoài. Nếu tài liệu không có thông tin → nói rõ "Tài liệu không đề cập".

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
            
            # Very low temperature for RAG (strict faithfulness to documents)
            temperature = 0.1
            
            print(f"🤖 RAG using {provider_name} | model: {model_identifier} | complexity: {complexity} | temp: {temperature}")
            
            answer = self.model_manager.generate_text(
                provider_name=provider_name,
                model_identifier=model_identifier,
                prompt=user_prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=6000
            )
            
            return answer
        
        except Exception as e:
            logger.error(f"❌ Answer generation error: {e}")
            return f"Lỗi khi tạo câu trả lời: {e}"

    # =========================================================================
    # Multi-Document Helpers
    # =========================================================================

    def _is_multi_document_query(
        self, query: str, contexts: List[Dict[str, Any]]
    ) -> bool:
        """
        Detect if query is specifically about analyzing/summarizing multiple
        documents (and contexts actually span more than one document).
        """
        unique_docs = set(
            self._build_source_label(ctx)
            for ctx in contexts
        )
        if len(unique_docs) <= 1:
            return False

        multi_doc_keywords = [
            "tóm tắt", "summarize", "summary",
            "các file", "các tài liệu", "các document",
            "nhiều file", "nhiều tài liệu",
            "tất cả", "toàn bộ", "all",
            "từng file", "từng tài liệu", "each file", "each document",
            "mỗi file", "mỗi tài liệu",
            "so sánh", "compare", "khác nhau", "difference",
            "tổng hợp", "tổng kết", "phân tích các",
        ]
        query_lower = query.lower()
        return any(kw in query_lower for kw in multi_doc_keywords)

    def _group_contexts_by_document(
        self, contexts: List[Dict[str, Any]]
    ) -> OrderedDict:
        """Group contexts by their source document, preserving insertion order."""
        grouped: OrderedDict[str, List[Dict[str, Any]]] = OrderedDict()
        for ctx in contexts:
            doc_key = self._build_source_label(ctx)
            grouped.setdefault(doc_key, []).append(ctx)
        return grouped

    def _build_grouped_context_str(
        self, grouped: OrderedDict
    ) -> str:
        """Build a context string where chunks are grouped by document."""
        parts = []
        for doc_idx, (doc_name, doc_contexts) in enumerate(grouped.items(), 1):
            header = f"=== [{doc_name}] ==="
            chunks = "\n\n".join(
                f"[Đoạn {ci+1}]: {ctx['chunk_text']}"
                for ci, ctx in enumerate(doc_contexts)
            )
            parts.append(f"{header}\n{chunks}")
        return "\n\n".join(parts)

    def _build_history_section(
        self, chat_history: Optional[List[Dict[str, Any]]]
    ) -> str:
        """Build chat history section string for prompt."""
        if not chat_history:
            return ""
        # Keep 6 turns = 12 messages in the active prompt window.
        recent = chat_history[-12:]
        lines = []
        for msg in recent:
            role = "Người dùng" if msg.get("role") == "user" else "Trợ lý"
            content = msg.get("content", "")
            # Truncate very long messages to save tokens (decreased to 1000)
            if len(content) > 1000:
                content = content[:1000] + "\n...[truncated]"
            lines.append(f"{role}: {content}")
        return "\nLỊCH SỬ TRÒ CHUYỆN GẦN ĐÂY:\n" + "\n".join(lines) + "\n"

    def _build_summary_section(self, conversation_summary: Optional[str]) -> str:
        if not conversation_summary:
            return ""
        text = conversation_summary.strip()
        if not text:
            return ""
        if len(text) > 3000:
            text = text[:3000] + "\n...[truncated]"
        return f"\nTÓM TẮT HỘI THOẠI TRƯỚC ĐÓ:\n{text}\n"

    def _build_source_metadata_section(
        self,
        source_metadata: Optional[List[Dict[str, Any]]],
    ) -> str:
        if not source_metadata:
            return ""

        lines = []
        for source in source_metadata[:10]:
            source_id = source.get("source_id") or "unknown"
            file_name = source.get("file_name") or (source.get("metadata") or {}).get("title") or source_id
            mime_type = source.get("mime_type") or "unknown"
            tags = (source.get("metadata") or {}).get("tags") or []
            tag_text = ", ".join(tags[:5]) if tags else "none"
            lines.append(f"- {file_name} | source_id={source_id} | mime={mime_type} | tags={tag_text}")

        if not lines:
            return ""

        return "\nMETADATA NGUỒN TRI THỨC ĐANG LIÊN QUAN:\n" + "\n".join(lines) + "\n"

    # =========================================================================
    # Map-Reduce Pipeline for Multi-Document Queries
    # =========================================================================

    async def _generate_map_reduce_answer(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        complexity: str = "moderate",
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Map-Reduce answer generation for multi-document queries.

        Map phase:  For each document, extract key information relevant to the
                    user query (one LLM call per document).
        Reduce phase: Synthesize per-document summaries into a coherent final
                      answer that analyses each document separately, then
                      highlights relationships and differences.
        """
        grouped = self._group_contexts_by_document(contexts)

        # ── MAP phase ─────────────────────────────────────────────────────
        map_system = (
            "Bạn là trợ lý phân tích tài liệu. Hãy trích xuất và tóm tắt "
            "các ý chính từ đoạn trích tài liệu dưới đây.\n\n"
            "YÊU CẦU:\n"
            "- Tóm tắt các ý chính, khái niệm quan trọng\n"
            "- Giữ nguyên thuật ngữ chuyên môn\n"
            "- Nêu rõ chủ đề/nội dung chính của tài liệu\n"
            "- Giải thích ngắn gọn các khái niệm, KHÔNG chỉ liệt kê từ khóa\n"
            "- Tối đa 200 từ\n"
            "- Dùng bullet points cho rõ ràng"
        )

        per_doc_summaries = []
        for doc_name, doc_contexts in grouped.items():
            doc_text = "\n\n".join(ctx["chunk_text"] for ctx in doc_contexts)
            map_prompt = (
                f"TÀI LIỆU: {doc_name}\n\nNỘI DUNG:\n{doc_text}\n\n"
                f"CÂU HỎI NGƯỜI DÙNG: {query}\n\n"
                "Trích xuất ý chính liên quan đến câu hỏi:"
            )

            try:
                provider, model = self.model_manager.get_model("document_map", "low")
                summary = self.model_manager.generate_text(
                    provider_name=provider,
                    model_identifier=model,
                    prompt=map_prompt,
                    system_instruction=map_system,
                    temperature=0.2,
                    max_tokens=600,
                )
                per_doc_summaries.append(
                    {"doc_name": doc_name, "summary": summary.strip()}
                )
            except Exception as e:
                logger.warning(f"⚠️ Map phase failed for {doc_name}: {e}")
                per_doc_summaries.append(
                    {"doc_name": doc_name, "summary": doc_text[:800]}
                )

        logger.info(
            f"📊 Map phase complete: {len(per_doc_summaries)} document summaries"
        )

        # ── REDUCE phase ──────────────────────────────────────────────────
        reduce_context = "\n\n".join(
            f"=== TÀI LIỆU: {s['doc_name']} ===\n{s['summary']}"
            for s in per_doc_summaries
        )

        history_section = self._build_history_section(chat_history)

        reduce_system = self._get_multi_document_system_prompt(
            complexity, len(grouped)
        )

        reduce_prompt = (
            f"PHÂN TÍCH TỪNG TÀI LIỆU:\n{reduce_context}"
            f"{history_section}\n"
            f"CÂU HỎI: {query}\n\n"
            "TRẢ LỜI (phân tích riêng từng tài liệu rồi tổng hợp):"
        )

        model_complexity = {
            "simple": "low",
            "moderate": "medium",
            "complex": "high",
        }.get(complexity, "medium")

        provider_name, model_identifier = self.model_manager.get_model(
            task_type="rag_query", complexity=model_complexity
        )
        temperature = 0.2 if complexity in ("moderate", "complex") else 0.5

        logger.info(
            f"🤖 Map-Reduce REDUCE using {provider_name} | model: "
            f"{model_identifier} | docs: {len(grouped)} | complexity: {complexity}"
        )

        answer = self.model_manager.generate_text(
            provider_name=provider_name,
            model_identifier=model_identifier,
            prompt=reduce_prompt,
            system_instruction=reduce_system,
            temperature=temperature,
            max_tokens=4000,
        )

        return answer

    def _get_multi_document_system_prompt(
        self, complexity: str, num_docs: int
    ) -> str:
        """System prompt for multi-document analysis (Reduce phase)."""
        return (
            f"Bạn là trợ lý phân tích tài liệu chuyên nghiệp. "
            f"Bạn được cung cấp phân tích của {num_docs} tài liệu riêng biệt.\n\n"
            "NGUYÊN TẮC:\n"
            "✅ **PHÂN TÍCH RIÊNG**: Phân tích từng tài liệu MỘT CÁCH RIÊNG BIỆT trước\n"
            "✅ **TỔNG HỢP**: Sau đó tổng hợp các điểm chung và điểm riêng\n"
            "✅ **CẤU TRÚC RÕ RÀNG**: Dùng heading rõ ràng cho từng tài liệu\n"
            "✅ **TRÍCH DẪN**: Ghi rõ thông tin đến từ tài liệu nào\n"
            "✅ **KẾT NỐI**: Chỉ ra mối liên hệ, tiến trình, hoặc sự khác biệt "
            "giữa các tài liệu\n"
            "✅ **GIẢI THÍCH**: Giải thích ý nghĩa các khái niệm, KHÔNG chỉ liệt kê "
            "từ khóa\n\n"
            "CẤU TRÚC TRẢ LỜI:\n\n"
            "### 📄 Tài liệu 1: [Tên]\n"
            "- Nội dung chính, ý chính\n"
            "- Các khái niệm/thuật ngữ quan trọng kèm giải thích\n\n"
            "### 📄 Tài liệu 2: [Tên]\n"
            "- Nội dung chính, ý chính\n"
            "- Các khái niệm/thuật ngữ quan trọng kèm giải thích\n\n"
            "[... tiếp tục cho từng tài liệu ...]\n\n"
            "### 🔗 Tổng hợp & So sánh\n"
            "- Điểm chung giữa các tài liệu\n"
            "- Điểm riêng/khác biệt\n"
            "- Mối liên hệ/tiến trình (nếu có)\n\n"
            "### 💡 Kết luận\n"
            "- Tóm tắt tổng thể\n"
            "- Gợi ý tìm hiểu thêm\n\n"
            "YÊU CẦU:\n"
            "✅ Dựa HOÀN TOÀN vào tài liệu\n"
            "✅ Phân tích TỪNG tài liệu riêng biệt\n"
            "✅ KHÔNG gộp chung các tài liệu lại\n"
            "✅ Giải thích mối quan hệ giữa các khái niệm, không chỉ liệt kê "
            "từ khóa\n"
            "✅ Kết thúc hoàn chỉnh, không dang dở"
        )
    
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

⛔ NGUYÊN TẮC TUYỆT ĐỐI - PHẢI TUÂN THỦ:
1. CHỈ trả lời dựa trên thông tin CÓ TRONG tài liệu được cung cấp bên dưới
2. TUYỆT ĐỐI KHÔNG thêm kiến thức bên ngoài, KHÔNG suy luận, KHÔNG bịa đặt
3. Nếu tài liệu KHÔNG đề cập đến câu hỏi → trả lời: "Tài liệu không đề cập đến nội dung này."
4. KHÔNG mở rộng, KHÔNG giải thích thêm ngoài những gì tài liệu viết

YÊU CẦU:
✅ Trả lời TRỰC TIẾP từ tài liệu
✅ Chỉ 1-3 câu
✅ Trích dẫn nguồn bằng TÊN FILE trong ngoặc vuông: "Theo [tên_file.pdf], ..."
✅ KHÔNG giải thích dài dòng
✅ KHÔNG dùng heading/format phức tạp

VÍ DỤ:
- "Định nghĩa X?" → "Theo [bai_giang.pdf], X là..."
- "Công thức Y?" → "Y = ... (theo [chuong3.docx])"
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

QUY TẮC TRÍCH DẪN:
✅ Trích dẫn bằng TÊN FILE trong ngoặc vuông: "Theo [tên_file.pdf], ..."
✅ KHÔNG dùng cách trích dẫn "Tài liệu 1", "Tài liệu 2" - phải dùng tên file thực
✅ Kết thúc hoàn chỉnh, không dang dở

VÍ DỤ:
YC: "Viết đoạn văn 200 chữ về bảo vệ môi trường từ tài liệu"
TL: "Theo [moi_truong.pdf], bảo vệ môi trường là trách nhiệm..."

❌ KHÔNG TRẢ LỜI KIỂU:
"Theo Tài liệu 1: ..."
"Tài liệu 2 cho thấy..."
"""
            
            # ANALYTICAL MODE: Trả lời câu hỏi từ tài liệu
            else:
                return """Bạn là trợ lý học tập chuyên môn. Trả lời CHÍNH XÁC và ĐẦY ĐỦ dựa trên tài liệu.

⛔ NGUYÊN TẮC TUYỆT ĐỐI - PHẢI TUÂN THỦ:
1. CHỈ trả lời dựa trên thông tin CÓ TRONG tài liệu được cung cấp bên dưới
2. TUYỆT ĐỐI KHÔNG thêm kiến thức bên ngoài, KHÔNG suy luận vượt quá nội dung tài liệu
3. TUYỆT ĐỐI KHÔNG bịa đặt thông tin không có trong tài liệu
4. Nếu tài liệu KHÔNG đề cập → NÓI RÕ: "Tài liệu không đề cập đến nội dung này."
5. Mọi câu trả lời PHẢI trích dẫn cụ thể từ đoạn nào trong tài liệu

NGUYÊN TẮC CHẤT LƯỢNG:
✅ **CHÍNH XÁC tuyệt đối**: Chỉ dựa vào tài liệu cung cấp
✅ **ĐẦY ĐỦ**: Không bỏ sót thông tin quan trọng từ tài liệu
✅ **TRÍCH DẪN RÕ RÀNG**: Trích dẫn bằng TÊN FILE trong ngoặc vuông: "Theo [tên_file.pdf], ..."
✅ **CÓ CẤU TRÚC**: Dùng markdown để dễ đọc

FORMAT OUTPUT: Markdown (dùng **, -)

CẤU TRÚC:
- **Định nghĩa/Tóm tắt**: 1-2 câu ngắn gọn, trích dẫn từ tài liệu
- **Các thành phần/khía cạnh chính**: Liệt kê ĐẦY ĐỦ từ tài liệu
- **Giải thích**: Mỗi thành phần giải thích CHỈ theo nội dung tài liệu
- **Trích dẫn**: "Theo [tên_file.pdf], ..."

YÊU CẦU:
✅ Dựa HOÀN TOÀN vào tài liệu
✅ KHÔNG thêm kiến thức bên ngoài dù biết câu trả lời
✅ Dùng markdown: **bold**, - bullet
✅ CẤM bỏ sót thông tin quan trọng trong tài liệu
✅ KHÔNG dùng "Tài liệu 1", "Tài liệu 2" - phải dùng TÊN FILE thực

VÍ DỤ TRẢ LỜI TỐT:
"Theo [bai_giang_OOP.pdf], OOP có **4 nguyên lý cơ bản**: **Encapsulation** (đóng gói), **Inheritance** (kế thừa)..."

❌ VÍ DỤ TRẢ LỜI SAI (ảo giác):
"OOP là phương pháp lập trình hướng đối tượng..." (← tự thêm kiến thức, không trích dẫn tài liệu)
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

QUY TẮC TRÍCH DẪN:
✅ Trích dẫn bằng TÊN FILE trong ngoặc vuông: "Theo [tên_file.pdf], ..."
✅ KHÔNG dùng "Tài liệu 1", "Tài liệu 2" - phải dùng tên file thực

VÍ DỤ:
YC: "Viết bài phân tích dựa trên tài liệu"
TL: "Theo [research_paper.pdf], nghiên cứu cho thấy..."
"""
            
            # ANALYTICAL MODE: Phân tích chuyên sâu từ tài liệu
            else:
                return """Bạn là trợ lý học tập chuyên sâu. Trả lời CHI TIẾT và TOÀN DIỆN dựa trên tài liệu.

⛔ NGUYÊN TẮC TUYỆT ĐỐI - PHẢI TUÂN THỦ:
1. CHỈ trả lời dựa trên thông tin CÓ TRONG tài liệu được cung cấp bên dưới
2. TUYỆT ĐỐI KHÔNG thêm kiến thức bên ngoài, KHÔNG suy luận vượt quá nội dung tài liệu
3. TUYỆT ĐỐI KHÔNG bịa đặt thông tin không có trong tài liệu
4. Nếu tài liệu KHÔNG đề cập → NÓI RÕ: "Tài liệu không đề cập đến nội dung này."
5. Mọi câu trả lời PHẢI trích dẫn cụ thể từ đoạn nào trong tài liệu
6. Khi tài liệu mô tả mô hình/kiến trúc, PHẢI mô tả CHÍNH XÁC theo tài liệu, KHÔNG thay thế bằng kiến thức chung

NGUYÊN TẮC CHẤT LƯỢNG:
✅ **CHÍNH XÁC tuyệt đối**: Chỉ dựa vào tài liệu cung cấp
✅ **ĐẦY ĐỦ**: Bao gồm TẤT CẢ thông tin quan trọng từ tài liệu
✅ **CÓ CHIỀU SÂU**: Phân tích kỹ lưỡng, kết nối các ý TRONG tài liệu
✅ **TRÍCH DẪN cụ thể**: Trích dẫn bằng TÊN FILE trong ngoặc vuông: "Theo [tên_file.pdf], ..."
✅ **CÓ CẤU TRÚC**: Markdown với heading và formatting

FORMAT OUTPUT: Markdown (dùng ###, **, -, 1.)

CẤU TRÚC TRẢ LỜI:

### 1. Tóm Tắt
2-3 câu tóm tắt ngắn gọn, trích dẫn trực tiếp từ tài liệu

### 2. Các Điểm Chính
Liệt kê **ĐẦY ĐỦ TẤT CẢ** các điểm quan trọng từ tài liệu:
1. **Điểm 1**: Mô tả chi tiết ĐÚNG NHƯ tài liệu viết
   - Trích dẫn: "Theo [tên_file.pdf], ..."
2. **Điểm 2**: Mô tả chi tiết ĐÚNG NHƯ tài liệu viết
   - Trích dẫn: "Theo [tên_file.pdf], ..."
(Tiếp tục cho đến hết)

### 3. Giải Thích Chi Tiết
- Phân tích TỪNG ĐIỂM đã liệt kê, CHỈ dựa trên nội dung tài liệu
- Làm rõ mối liên hệ giữa các điểm NHƯ tài liệu trình bày
- Kèm ví dụ cụ thể từ tài liệu (nếu tài liệu có ví dụ)
- Trích dẫn rõ ràng: "**Theo [tên_file.pdf]**, ..."

### 4. Kết Luận
- Tóm lại các điểm chính từ tài liệu
- Gợi ý câu hỏi liên quan để tìm hiểu thêm

YÊU CẦU:
✅ Dựa HOÀN TOÀN vào tài liệu (KHÔNG tự thêm kiến thức dù biết câu trả lời)
✅ Chi tiết (~400-800 từ)
✅ CẤM bỏ sót thông tin quan trọng
✅ Trích dẫn cụ thể từng phần bằng TÊN FILE trong ngoặc vuông
✅ KHÔNG dùng "Tài liệu 1", "Tài liệu 2" - phải dùng tên file thực

❌ VÍ DỤ TRẢ LỜI SAI (ảo giác):
- Trả lời theo kiến thức chung về chủ đề mà không trích dẫn tài liệu
- Mô tả mô hình khác với mô hình trong tài liệu
- Thêm thông tin "bổ sung" không có trong tài liệu
"""


    # =========================================================================
    # Summarization Pipeline
    # =========================================================================

    def _is_summarization_query(self, query: str) -> bool:
        """Detect if query is a summarization request."""
        keywords = [
            "tóm tắt", "summarize", "summary", "tổng hợp", "tổng kết",
            "nội dung chính", "điểm chính", "key points", "overview",
            "tóm lại", "tóm gọn", "nói về gì", "bài này về",
        ]
        query_lower = query.lower()
        return any(kw in query_lower for kw in keywords)

    async def _retrieve_full_document(
        self,
        user_id: str,
        document_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Retrieve ALL chunks from ALL specified documents using scroll (not search)."""
        try:
            all_contexts = []

            # Scroll per document to avoid limit issues
            for doc_id in document_ids:
                filter_conditions = [
                    FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                    FieldCondition(key="document_id", match=MatchValue(value=doc_id))
                ]
                query_filter = Filter(must=filter_conditions)

                offset = None
                while True:
                    results, next_offset = qdrant_manager.client.scroll(
                        collection_name=qdrant_manager.collection_name,
                        scroll_filter=query_filter,
                        limit=100,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False
                    )

                    for result in results:
                        all_contexts.append({
                            "chunk_id": result.id,
                            "score": 1.0,
                            "chunk_text": result.payload.get("chunk_text", ""),
                            "chunk_index": result.payload.get("chunk_index", 0),
                            "document_id": result.payload.get("document_id", ""),
                            "file_name": result.payload.get("file_name", ""),
                            "title": result.payload.get("title", "")
                        })

                    if next_offset is None:
                        break
                    offset = next_offset

            # Sort by document_id then chunk_index
            all_contexts.sort(
                key=lambda x: (x["document_id"], x["chunk_index"])
            )

            logger.info(
                f"📄 Full document retrieval: {len(all_contexts)} chunks "
                f"from {len(document_ids)} documents"
            )
            return all_contexts

        except Exception as e:
            logger.error(f"❌ Full document retrieval error: {e}")
            return []

    async def _execute_summarization(
        self,
        query: str,
        user_id: str,
        session_id: str,
        document_ids: List[str],
        chat_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Dedicated summarization pipeline.
        Scrolls ALL chunks from ALL documents, then uses Map-Reduce
        to summarize each document separately before combining.
        """
        # 1. Retrieve ALL chunks from ALL documents
        contexts = await self._retrieve_full_document(
            user_id=user_id,
            document_ids=document_ids
        )

        if not contexts:
            return {
                "answer": "Không tìm thấy nội dung tài liệu để tóm tắt.",
                "contexts": [],
                "metadata": {"no_context_found": True}
            }

        # 2. Group by document
        grouped = self._group_contexts_by_document(contexts)
        num_docs = len(grouped)
        logger.info(f"📝 Summarizing {num_docs} document(s)")

        # 3. Map phase: summarize each document individually
        map_system = (
            "Bạn là trợ lý tóm tắt tài liệu chuyên nghiệp.\n\n"
            "NHIỆM VỤ: Tóm tắt nội dung tài liệu sau đây.\n\n"
            "YÊU CẦU:\n"
            "- Nêu rõ chủ đề/nội dung chính\n"
            "- Liệt kê các điểm quan trọng bằng bullet points\n"
            "- Giải thích ngắn gọn từng điểm\n"
            "- Giữ nguyên thuật ngữ chuyên môn\n"
            "- Tối đa 300 từ\n"
            "- Bằng tiếng Việt"
        )

        per_doc_summaries = []
        for doc_name, doc_contexts in grouped.items():
            doc_text = "\n\n".join(ctx["chunk_text"] for ctx in doc_contexts)
            # Get document_id from first context
            doc_id = doc_contexts[0].get("document_id", "") if doc_contexts else ""

            summary = self._generate_map_summary_with_guard(
                doc_name=doc_name,
                doc_text=doc_text,
                base_system_prompt=map_system,
            )

            per_doc_summaries.append({
                "doc_name": doc_name,
                "doc_id": doc_id,
                "summary": summary
            })

        logger.info(f"📊 Map phase complete: {len(per_doc_summaries)} document summaries")

        # 4. Reduce phase: combine all summaries
        if num_docs == 1:
            # Single document — just use the map summary directly
            s = per_doc_summaries[0]
            answer = f"### 📄 Tóm tắt [{s['doc_name']}]\n\n{s['summary']}"
        else:
            # Multiple documents — use LLM to create combined summary
            reduce_context = "\n\n".join(
                f"=== [{s['doc_name']}] ===\n{s['summary']}"
                for s in per_doc_summaries
            )

            reduce_system = (
                f"Bạn là trợ lý tóm tắt chuyên nghiệp. "
                f"Bạn được cung cấp bản tóm tắt của {num_docs} tài liệu riêng biệt.\n\n"
                "CẤU TRÚC TRẢ LỜI BẮT BUỘC:\n\n"
                "Với MỖI tài liệu, viết theo format:\n"
                "### 📄 [tên_file]\n"
                "- Nội dung chính, ý chính\n"
                "- Các khái niệm/thuật ngữ quan trọng\n\n"
                "[... lặp lại cho từng tài liệu ...]\n\n"
                "### 🔗 Tổng hợp\n"
                "- Điểm chung giữa các tài liệu (nếu có)\n"
                "- Điểm riêng/khác biệt\n\n"
                "YÊU CẦU:\n"
                "✅ Tóm tắt RIÊNG BIỆT từng tài liệu, KHÔNG gộp chung\n"
                "✅ Dùng TÊN FILE trong ngoặc vuông [tên_file] làm heading\n"
                "✅ KHÔNG dùng 'Tài liệu 1', 'Tài liệu 2'\n"
                "✅ Giải thích rõ ràng nội dung, không chỉ liệt kê từ khóa\n"
                "✅ Bằng tiếng Việt"
            )

            reduce_prompt = (
                f"TÓM TẮT TỪNG TÀI LIỆU:\n{reduce_context}\n\n"
                f"YÊU CẦU CỦA NGƯỜI DÙNG: {query}\n\n"
                "TRẢ LỜI (tóm tắt riêng từng tài liệu rồi tổng hợp):"
            )

            try:
                provider, model = self.model_manager.get_model("summarization", "high")
                answer = self.model_manager.generate_text(
                    provider_name=provider,
                    model_identifier=model,
                    prompt=reduce_prompt,
                    system_instruction=reduce_system,
                    temperature=0.3,
                    max_tokens=4000,
                )
            except Exception as e:
                logger.error(f"❌ Reduce phase error: {e}")
                # Fallback: concatenate per-doc summaries
                parts = []
                for s in per_doc_summaries:
                    parts.append(f"### 📄 [{s['doc_name']}]\n\n{s['summary']}")
                answer = "\n\n".join(parts)

        # 5. Save state
        self.save_state(user_id, session_id, {
            "last_query": query,
            "contexts_used": len(contexts)
        })
        self.memory.set_context(user_id, session_id, "last_action", "summarization")

        # Build doc_map for frontend clickable links
        doc_map = self._build_doc_map(contexts)

        return {
            "answer": answer,
            "contexts": contexts[:20],  # Return sample contexts
            "metadata": {
                "model": "gemini-pro",
                "contexts_count": len(contexts),
                "retrieval_mode": "full_document_scroll",
                "pipeline": {"pipeline": "summarization_map_reduce"},
                "doc_map": doc_map,
                **self.build_quota_metadata(answer)
            }
        }

    def _generate_map_summary_with_guard(
        self,
        doc_name: str,
        doc_text: str,
        base_system_prompt: str,
    ) -> str:
        """
        Generate per-document summary with quality guard.
        If output is too short or looks cut off, retry with stricter prompt.
        """
        if not doc_text.strip():
            return "(Tài liệu không có nội dung văn bản để tóm tắt.)"

        base_prompt = (
            f"TÀI LIỆU: {doc_name}\n\n"
            f"NỘI DUNG:\n{doc_text}\n\n"
            "Tóm tắt nội dung chính của tài liệu này:"
        )

        strict_system = (
            "Bạn là trợ lý tóm tắt tài liệu chất lượng cao.\n\n"
            "BẮT BUỘC:\n"
            "- Trả lời bằng tiếng Việt\n"
            "- Viết đầy đủ, không dừng giữa câu\n"
            "- Độ dài tối thiểu khoảng 350 từ với tài liệu dài\n"
            "- Có cấu trúc: Chủ đề chính, Các điểm chính (bullet), Kết luận\n"
            "- Nếu tài liệu ngắn thì tóm tắt ngắn nhưng vẫn phải kết thúc trọn ý"
        )
        strict_prompt = (
            f"TÀI LIỆU: {doc_name}\n\n"
            f"NỘI DUNG:\n{doc_text}\n\n"
            "Hãy tóm tắt đầy đủ theo đúng cấu trúc yêu cầu. "
            "Không được trả lời cụt hoặc dừng giữa câu."
        )

        attempts = [
            {
                "force_provider": None,
                "system": base_system_prompt,
                "prompt": base_prompt,
                "temperature": 0.3,
                "max_tokens": 1200,
            },
            {
                "force_provider": "mistral",
                "system": strict_system,
                "prompt": strict_prompt,
                "temperature": 0.2,
                "max_tokens": 1800,
            },
            {
                "force_provider": "gemini",
                "system": strict_system,
                "prompt": strict_prompt,
                "temperature": 0.2,
                "max_tokens": 1800,
            },
        ]

        best_summary = ""
        for idx, cfg in enumerate(attempts, start=1):
            try:
                provider, model = self.model_manager.get_model(
                    "summarization",
                    "high",
                    force_provider=cfg["force_provider"],
                )
                summary = self.model_manager.generate_text(
                    provider_name=provider,
                    model_identifier=model,
                    prompt=cfg["prompt"],
                    system_instruction=cfg["system"],
                    temperature=cfg["temperature"],
                    max_tokens=cfg["max_tokens"],
                ).strip()

                if len(summary) > len(best_summary):
                    best_summary = summary

                if not self._is_summary_too_short_or_cut(summary, len(doc_text)):
                    if idx > 1:
                        logger.info(
                            f"✅ Summary guard recovered on attempt {idx} for {doc_name}"
                        )
                    return summary
            except Exception as e:
                logger.warning(f"⚠️ Summary attempt {idx} failed for {doc_name}: {e}")

        if best_summary:
            logger.warning(
                f"⚠️ Summary quality still low for {doc_name}; returning longest available output"
            )
            return best_summary

        return doc_text[:1200]

    def _is_summary_too_short_or_cut(self, summary: str, source_len: int) -> bool:
        text = (summary or "").strip()
        if not text:
            return True

        # Dynamic minimum length based on source size.
        min_chars = 300
        if source_len > 6000:
            min_chars = 500
        elif source_len > 3000:
            min_chars = 400

        if len(text) < min_chars:
            return True

        if len(text) >= 40 and not re.search(r"[.!?…\]\)\"”']\s*$", text):
            return True

        return False

    # =========================================================================
    # Helper: Build document map for frontend link resolution
    # =========================================================================

    def _build_source_label(self, ctx: Dict[str, Any]) -> str:
        """Create a stable human-readable source label with short document id."""
        file_name = (ctx.get("file_name") or "Tài liệu").strip()
        doc_id = (ctx.get("document_id") or "").strip()
        if doc_id:
            return f"{file_name} | id:{doc_id[:8]}"
        return file_name

    def _build_doc_map(self, contexts: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Build a map of {file_name -> document_id} for frontend to create
        clickable links from document citations.
        """
        seen = set()
        doc_map = []
        for ctx in contexts:
            file_name = ctx.get("file_name", "")
            doc_id = ctx.get("document_id", "")
            source_label = self._build_source_label(ctx)
            seen_key = (source_label, doc_id)
            if file_name and doc_id and seen_key not in seen:
                doc_map.append({
                    "file_name": source_label,
                    "raw_file_name": file_name,
                    "document_id": doc_id
                })
                seen.add(seen_key)
        return doc_map


# Global singleton
document_qa_agent = DocumentQAAgent()
