"""
Master Orchestrator v2.0 - Multi-Agent Coordinator
Orchestrates multiple specialized agents with memory and context management
"""
from typing import Dict, Any, Optional, List
import time
import logging
import re

from core.config import settings
from core.memory import memory_manager
from core.qdrant import qdrant_manager
from services.intent_classifier import intent_classifier
from agents.prompt_preprocessor import prompt_preprocessor
from agents.document_qa_agent import document_qa_agent
from agents.data_analysis_agent import data_analysis_agent
from agents.general_qa_agent import general_qa_agent
from services.embedding_service import embedding_service
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

logger = logging.getLogger(__name__)

try:
    from core.model_manager import model_manager
except Exception:
    model_manager = None


class MasterOrchestrator:
    """
    Master Orchestrator - Coordinates all agents
    
    Workflow:
        1. Preprocess query (resolve ambiguity)
        2. Classify intent
        3. Route to appropriate agent
        4. Manage memory/context
        5. Return response
    """
    
    def __init__(self):
        """Initialize orchestrator"""
        self.memory = memory_manager
        self.intent_classifier = intent_classifier
        self.prompt_preprocessor = prompt_preprocessor
        
        # Agent registry
        self.agents = {
            "document_qa": document_qa_agent,
            "data_analysis": data_analysis_agent,
            "general_qa": general_qa_agent
        }
        
        logger.info("🎯 Master Orchestrator v2.0 initialized with Multi-Agent support")
        self._summary_update_every_messages = 10
        self._summary_max_messages_per_update = 40
    
    async def process_query(
        self,
        query: str,
        user_id: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point - Process query through multi-agent workflow
        
        Args:
            query: User query
            user_id: User ID
            session_id: Chat session ID
            context: Additional context:
                - document_ids: List of document IDs (for RAG)
                - file_path: Path to data file (for analysis)
                - file_name: Filename
                - file_data: File bytes
                - top_k: Number of contexts
                - score_threshold: Similarity threshold
        
        Returns:
            Dict with:
                - answer: Agent response
                - intent: Detected intent
                - agent_used: Which agent handled the request
                - metadata: Additional metadata
                - processing_time: Total time
        """
        start_time = time.time()
        context = context or {}
        
        try:
            logger.info(f"🚀 Processing query | User: {user_id} | Session: {session_id}")
            logger.info(f"📝 Query: {query[:100]}...")
            
            # Step 0: Ensure chat_history is available (fallback to Mongo memory)
            if not context.get("chat_history"):
                stored_history = self.memory.get_chat_history(user_id, session_id, limit=12)
                if stored_history:
                    context["chat_history"] = [
                        {"role": msg["role"], "content": msg["content"]}
                        for msg in stored_history
                    ]
                    logger.info(f"📝 Loaded {len(context['chat_history'])} messages from Mongo memory")

            # Step 0.1: Attach long-term conversation summary (if available).
            # This improves follow-up accuracy when the relevant context is older
            # than the short chat_history window.
            if not context.get("conversation_summary"):
                summary = self.memory.get_context(user_id, session_id, "conversation_summary")
                if isinstance(summary, str) and summary.strip():
                    context["conversation_summary"] = summary.strip()
            
            # Step 1: Preprocess query (resolve ambiguity)
            if settings.ENABLE_PROMPT_PREPROCESSING:
                preprocess_result = await self.prompt_preprocessor.execute(
                    query=query,
                    user_id=user_id,
                    session_id=session_id,
                    context=context
                )
                
                processed_query = preprocess_result["processed_query"]
                is_ambiguous = preprocess_result["is_ambiguous"]
                
                if is_ambiguous:
                    logger.info(f"🔍 Preprocessed: '{query}' → '{processed_query}'")
            else:
                processed_query = query
                is_ambiguous = False
            
            # Step 2: Classify intent
            document_ids = context.get("document_ids")
            has_documents = bool(document_ids and len(document_ids) > 0)
            has_data_file = self._has_tabular_data_file(context)
            document_count = len(document_ids) if document_ids else 0
            chat_history = context.get("chat_history") or []
            source_metadata = context.get("source_metadata") or []

            forced_intent = context.get("force_intent")
            intent_aliases = {
                "direct_chat": "qa",
                "rag_query": "qa",
                "summarization": "qa",
                "question_generation": "qa",
                "code_help": "qa",
                "homework_solver": "computation",
                "data_analysis": "analysis",
            }
            if forced_intent:
                intent = intent_aliases.get(forced_intent, forced_intent)
                context["forced_intent_raw"] = forced_intent
                logger.info(f"↪️ Forced intent: {intent}")
            else:
                intent = self.intent_classifier.classify(
                    question=processed_query,
                    has_documents=has_documents,
                    document_count=document_count,
                    chat_history=chat_history,
                    source_metadata=source_metadata,
                    has_tabular_data=has_data_file,
                )

            # Document grounding signals for QA/computation/analysis routing.
            doc_grounded = False
            if has_documents and self._should_force_document_grounding_by_retrieval(
                query=processed_query,
                user_id=user_id,
                document_ids=document_ids,
            ):
                doc_grounded = True
                logger.info("↪️ Document grounding: retrieval-based match")

            if self._should_force_document_grounding(
                query=processed_query,
                has_documents=has_documents,
                document_count=document_count,
            ):
                doc_grounded = True
                logger.info("↪️ Document grounding: deictic query")

            context["doc_grounded"] = doc_grounded
            
            logger.info(
                f"🎯 Intent: {intent} | Has docs: {has_documents} | Has data file: {has_data_file} | "
                f"Doc count: {document_count} | Doc grounded: {doc_grounded}"
            )
            
            # Step 3: Route to appropriate agent
            # Pass intent into context so agents can adjust their behaviour
            context["intent"] = intent
            result = await self._route_to_agent(
                intent=intent,
                query=processed_query,
                user_id=user_id,
                session_id=session_id,
                context=context
            )
            
            # Step 4: Save to memory only when backend has not persisted transcript.
            if not context.get("persisted_by_backend"):
                self._save_to_memory(
                    user_id=user_id,
                    session_id=session_id,
                    query=query,
                    processed_query=processed_query,
                    intent=intent,
                    result=result
                )

                # Update conversation summary after persisting messages.
                # This keeps a long-term memory that survives beyond the short
                # chat_history window for future turns.
                self._maybe_update_conversation_summary(user_id=user_id, session_id=session_id)
            
            # Step 5: Add metadata
            processing_time = time.time() - start_time
            
            result.update({
                "intent": intent,
                "preprocessing": {
                    "was_ambiguous": is_ambiguous,
                    "original_query": query if is_ambiguous else None,
                    "processed_query": processed_query if is_ambiguous else None
                },
                "processing_time": processing_time,
                "user_id": user_id,
                "session_id": session_id
            })
            
            logger.info(f"✅ Completed in {processing_time:.2f}s | Intent: {intent} | Agent: {result.get('agent_used', 'unknown')}")
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Orchestrator error: {e}", exc_info=True)
            return {
                "answer": f"Đã xảy ra lỗi khi xử lý câu hỏi: {e}",
                "intent": "error",
                "agent_used": "none",
                "metadata": {"error": str(e)},
                "processing_time": time.time() - start_time
            }
    
    async def _route_to_agent(
        self,
        intent: str,
        query: str,
        user_id: str,
        session_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Route query to appropriate agent based on intent
        
        Args:
            intent: Classified intent
            query: Processed query
            user_id: User ID
            session_id: Session ID
            context: Context dict
        
        Returns:
            Agent response
        """
        try:
            document_ids = context.get("document_ids") or []
            has_documents = bool(document_ids and len(document_ids) > 0)
            has_data_file = self._has_tabular_data_file(context)
            forced_intent_raw = (context.get("force_intent") or "").strip().lower()

            # Route based on intent
            # Hard guardrail: only route to data_analysis_agent when we are sure
            # the attached file is tabular (csv/xlsx) OR backend explicitly forces it.
            if intent in {"computation", "analysis"} and (has_data_file or forced_intent_raw == "data_analysis"):
                logger.info(f"📊 Routing to Data Analysis Agent (intent={intent})")
                result = await data_analysis_agent.execute(
                    query=query,
                    user_id=user_id,
                    session_id=session_id,
                    context=context
                )
                result["agent_used"] = "data_analysis_agent"

            elif has_documents and context.get("doc_grounded"):
                logger.info("📚 Routing to Document QA Agent (doc-grounded)")
                result = await document_qa_agent.execute(
                    query=query,
                    user_id=user_id,
                    session_id=session_id,
                    context=context
                )
                result["agent_used"] = "document_qa_agent"

            else:
                logger.info("💬 Routing to General QA Agent")
                result = await general_qa_agent.execute(
                    query=query,
                    user_id=user_id,
                    session_id=session_id,
                    context=context
                )
                result["agent_used"] = "general_qa_agent"
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Agent routing error: {e}")
            return {
                "answer": f"Lỗi khi xử lý với agent: {e}",
                "agent_used": "error",
                "metadata": {"error": str(e)}
            }
    
    def _save_to_memory(
        self,
        user_id: str,
        session_id: str,
        query: str,
        processed_query: str,
        intent: str,
        result: Dict[str, Any]
    ):
        """
        Save interaction to memory
        """
        try:
            # Save user message
            self.memory.add_message(
                user_id=user_id,
                session_id=session_id,
                role="user",
                content=query,
                metadata={
                    "processed_query": processed_query,
                    "intent": intent
                }
            )
            
            # Save assistant response
            self.memory.add_message(
                user_id=user_id,
                session_id=session_id,
                role="assistant",
                content=result.get("answer", ""),
                metadata={
                    "intent": intent,
                    "agent_used": result.get("agent_used", "unknown"),
                    "next_action": result.get("next_action")
                }
            )
            
            logger.debug(f"💾 Saved to memory | User: {user_id} | Session: {session_id}")
        
        except Exception as e:
            logger.error(f"❌ Memory save error: {e}")

    def _maybe_update_conversation_summary(self, user_id: str, session_id: str) -> None:
        """
        Auto-summarize conversation into a long-term `conversation_summary` stored in Mongo.

        Strategy:
        - Track `summary_up_to_sequence` in conversation_state.context.
        - When at least N new messages have arrived since last summary, summarize only
          the delta messages and merge into existing summary.
        - Uses model_manager with fallback chain for quota/rate-limit resilience.
        """
        if not getattr(self.memory, "enabled", False):
            return
        if model_manager is None:
            return

        try:
            last_seq = self.memory.get_last_sequence(user_id, session_id)
            summarized_up_to = self.memory.get_context(user_id, session_id, "summary_up_to_sequence")
            summarized_up_to = int(summarized_up_to or 0)

            # If conversation is short, skip to save tokens.
            new_count = max(0, last_seq - summarized_up_to)
            if new_count < self._summary_update_every_messages:
                return

            delta_messages = self.memory.get_messages_since_sequence(
                user_id=user_id,
                session_id=session_id,
                after_sequence_no=summarized_up_to,
                limit=self._summary_max_messages_per_update,
            )
            if not delta_messages:
                return

            existing_summary = self.memory.get_context(user_id, session_id, "conversation_summary") or ""
            existing_summary = existing_summary.strip() if isinstance(existing_summary, str) else ""

            # Build a compact delta transcript for the LLM.
            transcript_lines = []
            for msg in delta_messages:
                role = "User" if msg.get("role") == "user" else "Assistant"
                content = (msg.get("content") or "").strip()
                if len(content) > 600:
                    content = content[:600] + "..."
                transcript_lines.append(f"{role}: {content}")
            delta_text = "\n".join(transcript_lines).strip()

            system = (
                "Bạn là hệ thống tóm tắt hội thoại cho chatbot.\n\n"
                "MỤC TIÊU:\n"
                "- Duy trì một `conversation_summary` NGẮN GỌN nhưng đủ để mô hình hiểu ngữ cảnh lâu dài.\n"
                "- Summary phải giúp người dùng quay lại các ý cũ (A/B) sau nhiều lượt hỏi.\n\n"
                "QUY TẮC:\n"
                "- CHỈ tóm tắt, không bịa thêm.\n"
                "- Ưu tiên: (1) các ý chính A/B và trạng thái đã/đang làm, (2) kết luận/đáp án quan trọng,\n"
                "  (3) thuật ngữ/ký hiệu người dùng đang dùng, (4) câu hỏi còn dang dở.\n"
                "- Nếu có tài liệu/ảnh được nhắc, ghi lại tên file hoặc mô tả ngắn.\n\n"
                "OUTPUT FORMAT (tiếng Việt, gọn):\n"
                "### Tóm tắt dài hạn\n"
                "- Bối cảnh & mục tiêu\n"
                "- Ý A: trạng thái/kết luận\n"
                "- Ý B: trạng thái/kết luận\n"
                "- Các quyết định/giả định quan trọng\n"
                "- Việc còn lại / câu hỏi mở\n"
            )

            prompt = (
                "Bạn sẽ được cung cấp:\n"
                "1) Summary hiện tại (có thể rỗng)\n"
                "2) Các tin nhắn MỚI phát sinh kể từ lần tóm tắt trước\n\n"
                "Hãy cập nhật lại summary sao cho phản ánh toàn bộ cuộc trò chuyện đến hiện tại.\n\n"
                f"=== SUMMARY HIỆN TẠI ===\n{existing_summary or '(rỗng)'}\n"
                f"=== TIN NHẮN MỚI (DELTA) ===\n{delta_text}\n\n"
                "TRẢ LỜI BẰNG SUMMARY MỚI:"
            )

            provider, model = model_manager.get_model("summarization", "low")
            updated_summary = model_manager.generate_text(
                provider_name=provider,
                model_identifier=model,
                prompt=prompt,
                system_instruction=system,
                temperature=0.2,
                max_tokens=900,
            )
            updated_summary = (updated_summary or "").strip()
            if not updated_summary:
                return

            # Persist summary + checkpoint.
            self.memory.set_context(user_id, session_id, "conversation_summary", updated_summary)
            self.memory.set_context(user_id, session_id, "summary_up_to_sequence", last_seq)
            logger.info(
                f"🧠 Conversation summary updated: up_to_seq={last_seq} (delta={new_count} msgs)"
            )

        except Exception as e:
            logger.warning(f"⚠️ Auto-summary update failed (non-fatal): {e}")
    
    def get_chat_history(
        self,
        user_id: str,
        session_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get chat history for a session
        """
        return self.memory.get_chat_history(user_id, session_id, limit)
    
    def clear_session(
        self,
        user_id: str,
        session_id: str
    ) -> bool:
        """
        Clear session memory
        """
        try:
            self.memory.clear_chat_history(user_id, session_id)
            self.memory.clear_context(user_id, session_id)
            logger.info(f"🗑️ Cleared session | User: {user_id} | Session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Session clear error: {e}")
            return False

    def _should_force_document_grounding(
        self,
        query: str,
        has_documents: bool,
        document_count: int,
    ) -> bool:
        """
        Detect short/deictic requests that implicitly point to the currently
        attached documents (e.g. "giai bai nay", "lam cau nay", "this image").
        """
        if not has_documents or document_count <= 0:
            return False
        if not query:
            return False

        query_lower = query.lower().strip()
        if not query_lower:
            return False

        explicit_doc_markers = [
            "theo tai lieu", "theo tài liệu",
            "trong file", "trong tai lieu", "trong tài liệu",
            "file nay", "file này", "tai lieu nay", "tài liệu này",
            "hinh nay", "hình này", "anh nay", "ảnh này",
            "this file", "this document", "this image", "attached file",
        ]
        if any(marker in query_lower for marker in explicit_doc_markers):
            return True

        deictic_markers = [
            "này", "nay", "đó", "do", "kia", "ở trên", "o tren",
            "vừa gửi", "vua gui", "đính kèm", "dinh kem",
            "this", "that", "above", "attached",
        ]
        task_object_markers = [
            "bài", "bai", "bài tập", "bai tap", "đề", "de",
            "câu", "cau", "hình", "hinh", "ảnh", "anh",
            "file", "tài liệu", "tai lieu", "document", "image",
            "problem", "exercise", "question",
        ]

        has_deictic = any(marker in query_lower for marker in deictic_markers)
        has_task_object = any(marker in query_lower for marker in task_object_markers)
        short_or_medium = len(query_lower.split()) <= 18

        return has_deictic and has_task_object and short_or_medium

    def _should_force_document_grounding_by_retrieval(
        self,
        query: str,
        user_id: str,
        document_ids: Optional[List[str]],
    ) -> bool:
        if not query or not user_id or not document_ids:
            return False

    def _has_tabular_data_file(self, context: Dict[str, Any]) -> bool:
        """
        Determine whether the current context actually contains a tabular data file
        suitable for `data_analysis_agent` (CSV/XLSX). This prevents misrouting when
        some upstream layer always attaches file_data regardless of type.
        """
        try:
            file_name = (context.get("file_name") or "").lower().strip()
            file_path = (context.get("file_path") or "").lower().strip()

            # Most reliable: filename/path extension
            for candidate in (file_name, file_path):
                if candidate.endswith(".csv") or candidate.endswith(".xlsx") or candidate.endswith(".xls"):
                    return True

            # If backend passes source metadata, use mime/file hints
            source_metadata = context.get("source_metadata") or []
            for src in source_metadata:
                mime = (src.get("mime_type") or "").lower()
                name = (src.get("file_name") or "").lower()
                if mime in {
                    "text/csv",
                    "application/csv",
                    "application/vnd.ms-excel",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                }:
                    return True
                if name.endswith(".csv") or name.endswith(".xlsx") or name.endswith(".xls"):
                    return True

            # If we only have raw bytes but no type hints, treat as NOT tabular
            # to avoid false positives (e.g. images/docs).
            return False
        except Exception:
            return False

        try:
            query_vector = embedding_service.embed_query(query)
            query_filter = Filter(
                must=[
                    FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                    FieldCondition(key="document_id", match=MatchAny(any=document_ids)),
                ]
            )

            results = qdrant_manager.client.search(
                collection_name=qdrant_manager.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=1,
                with_payload=True,
            )

            if not results:
                return False

            top_score = results[0].score
            chunk_text = (results[0].payload or {}).get("chunk_text", "")

            query_tokens = [
                token
                for token in re.split(r"[^a-zA-Z0-9À-ỹ]+", query.lower())
                if len(token) >= 3
            ]
            if not query_tokens:
                return False

            chunk_lower = (chunk_text or "").lower()
            if not any(token in chunk_lower for token in query_tokens):
                return False
            min_score = min(
                settings.RAG_SCORE_THRESHOLD,
                max(settings.RAG_MIN_SCORE_THRESHOLD, 0.2),
            )
            return top_score >= min_score

        except Exception as e:
            logger.warning(f"⚠️ Retrieval grounding check failed: {e}")
            return False

    def _is_summarization_query(self, query: str) -> bool:
        query_lower = (query or "").lower()
        keywords = [
            "tóm tắt", "tom tat", "summarize", "summary",
            "tổng hợp", "tong hop", "tổng kết", "tong ket",
            "nội dung chính", "noi dung chinh", "overview",
            "file nói về", "file noi ve", "tai lieu noi ve", "tài liệu nói về",
        ]
        return any(keyword in query_lower for keyword in keywords)


# Global singleton
master_orchestrator = MasterOrchestrator()
