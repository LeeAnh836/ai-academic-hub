"""
Master Orchestrator v2.0 - Multi-Agent Coordinator
Orchestrates multiple specialized agents with memory and context management
"""
from typing import Dict, Any, Optional, List
import time
import logging

from core.config import settings
from core.memory import memory_manager
from services.intent_classifier import intent_classifier
from agents.prompt_preprocessor import prompt_preprocessor
from agents.document_qa_agent import document_qa_agent
from agents.data_analysis_agent import data_analysis_agent
from agents.general_qa_agent import general_qa_agent

logger = logging.getLogger(__name__)


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
            
            # Step 0: Ensure chat_history is available (fallback to Redis memory)
            if not context.get("chat_history"):
                redis_history = self.memory.get_chat_history(user_id, session_id, limit=10)
                if redis_history:
                    context["chat_history"] = [
                        {"role": msg["role"], "content": msg["content"]}
                        for msg in redis_history
                    ]
                    logger.info(f"📝 Loaded {len(context['chat_history'])} messages from Redis memory")
            
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
            has_documents = bool(document_ids and len(document_ids) > 0) or bool(context.get("file_path"))
            document_count = len(document_ids) if document_ids else 0
            
            intent = self.intent_classifier.classify(
                question=processed_query,
                has_documents=has_documents,
                document_count=document_count
            )

            # Safety guard:
            # If no file/document context is available, force model-knowledge answer
            # for document-dependent intents to avoid "không tìm thấy file" responses.
            if not has_documents and intent in {"rag_query", "summarization", "question_generation", "data_analysis"}:
                logger.info(
                    f"↪️ Override intent {intent} -> direct_chat (no document/file in session context)"
                )
                intent = "direct_chat"
            
            logger.info(f"🎯 Intent: {intent} | Has docs: {has_documents} | Doc count: {document_count}")
            
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
            
            # Step 4: Save to memory
            self._save_to_memory(
                user_id=user_id,
                session_id=session_id,
                query=query,
                processed_query=processed_query,
                intent=intent,
                result=result
            )
            
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
            # Route based on intent
            if intent == "rag_query":
                # Document QA Agent
                logger.info("📚 Routing to Document QA Agent")
                result = await document_qa_agent.execute(
                    query=query,
                    user_id=user_id,
                    session_id=session_id,
                    context=context
                )
                result["agent_used"] = "document_qa_agent"
            
            elif intent == "data_analysis":
                # Data Analysis Agent
                logger.info("📊 Routing to Data Analysis Agent")
                result = await data_analysis_agent.execute(
                    query=query,
                    user_id=user_id,
                    session_id=session_id,
                    context=context
                )
                result["agent_used"] = "data_analysis_agent"
            
            elif intent in ["summarization", "question_generation"]:
                # Document QA Agent (handles these too)
                logger.info(f"📚 Routing to Document QA Agent ({intent})")
                result = await document_qa_agent.execute(
                    query=query,
                    user_id=user_id,
                    session_id=session_id,
                    context=context
                )
                result["agent_used"] = "document_qa_agent"
            
            elif intent in ["direct_chat", "homework_solver", "code_help"]:
                # General QA Agent
                logger.info(f"💬 Routing to General QA Agent ({intent})")
                result = await general_qa_agent.execute(
                    query=query,
                    user_id=user_id,
                    session_id=session_id,
                    context=context
                )
                result["agent_used"] = "general_qa_agent"
            
            else:
                # Fallback to general QA
                logger.warning(f"⚠️ Unknown intent: {intent}, using General QA Agent")
                result = await general_qa_agent.execute(
                    query=query,
                    user_id=user_id,
                    session_id=session_id,
                    context=context
                )
                result["agent_used"] = "general_qa_agent (fallback)"
            
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


# Global singleton
master_orchestrator = MasterOrchestrator()
