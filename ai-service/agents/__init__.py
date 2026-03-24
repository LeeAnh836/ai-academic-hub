"""
Base Agent Class
Abstract base class for all specialized agents
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

from core.memory import memory_manager
from core.model_manager import model_manager

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents
    """
    
    def __init__(self, agent_name: str, description: str):
        """
        Initialize base agent
        
        Args:
            agent_name: Unique agent identifier
            description: Agent description
        """
        self.agent_name = agent_name
        self.description = description
        self.memory = memory_manager
        self.model_manager = model_manager
        
        logger.info(f"🤖 Initialized {self.agent_name}: {self.description}")
    
    @abstractmethod
    async def execute(
        self,
        query: str,
        user_id: str,
        session_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute agent task
        
        Args:
            query: User query (preprocessed)
            user_id: User ID
            session_id: Chat session ID
            context: Context dict with metadata
        
        Returns:
            Dict with:
                - answer: Agent response
                - metadata: Additional metadata
                - next_action: Optional next action suggestion
        """
        pass
    
    def save_state(
        self,
        user_id: str,
        session_id: str,
        state: Dict[str, Any]
    ):
        """Save agent state to memory"""
        self.memory.set_agent_state(user_id, session_id, self.agent_name, state)
    
    def load_state(
        self,
        user_id: str,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load agent state from memory"""
        return self.memory.get_agent_state(user_id, session_id, self.agent_name)
    
    def log_execution(
        self,
        user_id: str,
        session_id: str,
        query: str,
        result: Dict[str, Any]
    ):
        """Log agent execution"""
        logger.info(
            f"🤖 {self.agent_name} | User: {user_id} | "
            f"Session: {session_id} | Query: {query[:50]}..."
        )

    def build_quota_metadata(self, answer: str = "") -> Dict[str, Any]:
        """Build quota metadata for UI when rate-limit/quota errors are detected."""
        quota_info = self.model_manager.get_quota_status(error_message=answer)
        if quota_info.get("has_quota_issue"):
            return {"quota_info": quota_info}
        return {}
