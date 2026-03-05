"""
Prompt Preprocessor Agent
Preprocesses ambiguous queries using memory context
"""
from typing import Dict, Any, Optional
import logging

from agents import BaseAgent
from core.memory import memory_manager

logger = logging.getLogger(__name__)


class PromptPreprocessor(BaseAgent):
    """
    Preprocesses prompts to resolve ambiguous queries
    
    Examples:
        - "có" → "Có, tôi muốn bạn thực hiện phân tích dữ liệu"
        - "được" → "Được, hãy tạo biểu đồ cho kết quả"
        - "ok" → "OK, tiếp tục với phân tích"
    """
    
    def __init__(self):
        super().__init__(
            agent_name="prompt_preprocessor",
            description="Resolves ambiguous queries using conversation memory"
        )
        
        # Ambiguous keywords that need context
        self.ambiguous_keywords = [
            "có", "được", "ok", "oke", "yes", "no", "không",
            "tiếp tục", "dừng", "làm", "thực hiện", "xong",
            "đúng", "sai", "đồng ý", "từ chối"
        ]
    
    async def execute(
        self,
        query: str,
        user_id: str,
        session_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Preprocess query to resolve ambiguity
        
        Args:
            query: Original user query
            user_id: User ID
            session_id: Session ID
            context: Additional context
        
        Returns:
            Dict with:
                - processed_query: Enriched query
                - is_ambiguous: Whether query was ambiguous
                - original_query: Original query
        """
        try:
            # Check if query is ambiguous
            is_ambiguous = self._is_ambiguous(query)
            
            if not is_ambiguous:
                # Query is clear, no preprocessing needed
                return {
                    "processed_query": query,
                    "is_ambiguous": False,
                    "original_query": query
                }
            
            # Query is ambiguous, need to enrich with context
            logger.info(f"🔍 Ambiguous query detected: '{query}'")
            
            enriched_query = await self._enrich_query(
                query, user_id, session_id, context
            )
            
            logger.info(f"✅ Enriched query: '{enriched_query}'")
            
            return {
                "processed_query": enriched_query,
                "is_ambiguous": True,
                "original_query": query,
                "enrichment_used": True
            }
        
        except Exception as e:
            logger.error(f"❌ Prompt preprocessing error: {e}")
            # Fallback to original query
            return {
                "processed_query": query,
                "is_ambiguous": False,
                "original_query": query,
                "error": str(e)
            }
    
    def _is_ambiguous(self, query: str) -> bool:
        """
        Check if query is ambiguous
        
        Criteria:
            - Very short (< 10 chars)
            - Only contains ambiguous keywords
            - No question words
        """
        query_lower = query.lower().strip()
        
        # Very short
        if len(query_lower) < 10:
            # Check if it's just an ambiguous keyword
            words = query_lower.split()
            if len(words) <= 2:
                if any(kw in query_lower for kw in self.ambiguous_keywords):
                    return True
        
        return False
    
    async def _enrich_query(
        self,
        query: str,
        user_id: str,
        session_id: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Enrich ambiguous query with memory context
        
        Strategy:
            1. Get last assistant message (question/proposal)
            2. Get conversation context
            3. Build enriched query
        """
        try:
            # Get last assistant message
            last_assistant_msg = self.memory.get_last_message(
                user_id, session_id, role="assistant"
            )
            
            # Get session context
            session_context = self.memory.get_all_context(user_id, session_id)
            
            # Build enriched query
            enriched = self._build_enriched_query(
                query,
                last_assistant_msg,
                session_context
            )
            
            return enriched
        
        except Exception as e:
            logger.error(f"❌ Query enrichment error: {e}")
            return query
    
    def _build_enriched_query(
        self,
        query: str,
        last_assistant_msg: Optional[Dict],
        context: Dict[str, Any]
    ) -> str:
        """
        Build enriched query from context
        
        Examples:
            Query: "có"
            Last msg: "Bạn có muốn tôi phân tích dữ liệu không?"
            → "Có, tôi muốn bạn phân tích dữ liệu"
            
            Query: "được"
            Last action: "data_analysis"
            Last file: "sales.csv"
            → "Được, hãy tiếp tục phân tích sales.csv"
        """
        query_lower = query.lower().strip()
        
        # Affirmative responses
        if query_lower in ["có", "yes", "ok", "oke", "được", "đồng ý", "đúng"]:
            # Get what user is agreeing to
            if last_assistant_msg:
                last_content = last_assistant_msg.get("content", "")
                
                # Extract the proposal/question
                proposal = self._extract_proposal(last_content)
                
                if proposal:
                    return f"Có, {proposal}"
            
            # Fallback: Use context
            last_action = context.get("last_action")
            if last_action:
                return f"Có, hãy tiếp tục với {last_action}"
            
            return "Có, hãy thực hiện"
        
        # Negative responses
        elif query_lower in ["không", "no", "từ chối", "dừng", "sai"]:
            return "Không, đừng thực hiện"
        
        # Continue action
        elif query_lower in ["tiếp tục", "làm", "thực hiện"]:
            last_action = context.get("last_action", "tác vụ trước đó")
            return f"Tiếp tục {last_action}"
        
        # Default: Add context
        last_action = context.get("last_action")
        if last_action:
            return f"{query} (liên quan đến {last_action})"
        
        return query
    
    def _extract_proposal(self, text: str) -> Optional[str]:
        """
        Extract proposal from assistant message
        
        Example:
            "Bạn có muốn tôi phân tích dữ liệu không?"
            → "phân tích dữ liệu"
        """
        text_lower = text.lower()
        
        # Pattern: "bạn có muốn [X] không?"
        if "bạn có muốn" in text_lower and "không" in text_lower:
            start = text_lower.find("bạn có muốn") + len("bạn có muốn")
            end = text_lower.find("không", start)
            proposal = text[start:end].strip()
            
            # Remove "tôi" at the beginning
            if proposal.startswith("tôi "):
                proposal = proposal[4:]
            
            return proposal
        
        # Pattern: "Có muốn [X] không?"
        if "có muốn" in text_lower and "không" in text_lower:
            start = text_lower.find("có muốn") + len("có muốn")
            end = text_lower.find("không", start)
            proposal = text[start:end].strip()
            return proposal
        
        return None


# Global singleton
prompt_preprocessor = PromptPreprocessor()
