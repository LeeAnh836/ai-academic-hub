"""
Memory Manager - Redis-based conversation memory
Manages chat history, context, and agent state
"""
import redis
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

from core.config import settings

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Redis-based memory manager for multi-agent conversations
    """
    
    def __init__(self):
        """Initialize Redis connection"""
        self.client = None
        self.enabled = False
        
    def connect(self):
        """Connect to Redis"""
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
            # Test connection
            self.client.ping()
            self.enabled = True
            logger.info(f"✅ Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}. Memory features disabled.")
            self.enabled = False
    
    def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            self.client.close()
            logger.info("🔌 Disconnected from Redis")
    
    # ============================================
    # Chat History Management
    # ============================================
    
    def add_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Add message to chat history
        
        Args:
            user_id: User ID
            session_id: Chat session ID
            role: "user" or "assistant"
            content: Message content
            metadata: Additional metadata (intent, agent_used, etc.)
        
        Returns:
            bool: Success status
        """
        if not self.enabled:
            return False
        
        try:
            key = f"chat:{user_id}:{session_id}"
            
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            }
            
            # Add to list
            self.client.rpush(key, json.dumps(message))
            
            # Set expiration
            self.client.expire(key, settings.MEMORY_TTL)
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Failed to add message: {e}")
            return False
    
    def get_chat_history(
        self,
        user_id: str,
        session_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get chat history for a session
        
        Args:
            user_id: User ID
            session_id: Chat session ID
            limit: Max messages to retrieve (last N messages)
        
        Returns:
            List of message dicts
        """
        if not self.enabled:
            return []
        
        try:
            key = f"chat:{user_id}:{session_id}"
            
            # Get last N messages
            messages = self.client.lrange(key, -limit, -1)
            
            return [json.loads(msg) for msg in messages]
        
        except Exception as e:
            logger.error(f"❌ Failed to get chat history: {e}")
            return []
    
    def get_last_message(
        self,
        user_id: str,
        session_id: str,
        role: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get last message from a session
        
        Args:
            user_id: User ID
            session_id: Chat session ID
            role: Filter by role (user/assistant)
        
        Returns:
            Last message dict or None
        """
        history = self.get_chat_history(user_id, session_id, limit=20)
        
        if role:
            # Filter by role
            filtered = [msg for msg in history if msg["role"] == role]
            return filtered[-1] if filtered else None
        
        return history[-1] if history else None
    
    def clear_chat_history(
        self,
        user_id: str,
        session_id: str
    ) -> bool:
        """Clear chat history for a session"""
        if not self.enabled:
            return False
        
        try:
            key = f"chat:{user_id}:{session_id}"
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to clear chat history: {e}")
            return False
    
    # ============================================
    # Context Management
    # ============================================
    
    def set_context(
        self,
        user_id: str,
        session_id: str,
        context_key: str,
        context_value: Any
    ) -> bool:
        """
        Set context variable for a session
        
        Examples:
            - last_action: "data_analysis"
            - last_file: "sales_data.csv"
            - pending_confirmation: "create_chart"
        
        Args:
            user_id: User ID
            session_id: Chat session ID
            context_key: Context variable name
            context_value: Value (will be JSON serialized)
        
        Returns:
            bool: Success status
        """
        if not self.enabled:
            return False
        
        try:
            key = f"context:{user_id}:{session_id}"
            
            # Store as hash field
            self.client.hset(
                key,
                context_key,
                json.dumps(context_value)
            )
            
            # Set expiration
            self.client.expire(key, settings.MEMORY_TTL)
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Failed to set context: {e}")
            return False
    
    def get_context(
        self,
        user_id: str,
        session_id: str,
        context_key: str
    ) -> Optional[Any]:
        """
        Get context variable
        
        Args:
            user_id: User ID
            session_id: Chat session ID
            context_key: Context variable name
        
        Returns:
            Context value or None
        """
        if not self.enabled:
            return None
        
        try:
            key = f"context:{user_id}:{session_id}"
            value = self.client.hget(key, context_key)
            
            if value:
                return json.loads(value)
            return None
        
        except Exception as e:
            logger.error(f"❌ Failed to get context: {e}")
            return None
    
    def get_all_context(
        self,
        user_id: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Get all context variables for a session
        
        Returns:
            Dict of context variables
        """
        if not self.enabled:
            return {}
        
        try:
            key = f"context:{user_id}:{session_id}"
            context = self.client.hgetall(key)
            
            # Deserialize all values
            return {
                k: json.loads(v)
                for k, v in context.items()
            }
        
        except Exception as e:
            logger.error(f"❌ Failed to get all context: {e}")
            return {}
    
    def clear_context(
        self,
        user_id: str,
        session_id: str
    ) -> bool:
        """Clear all context for a session"""
        if not self.enabled:
            return False
        
        try:
            key = f"context:{user_id}:{session_id}"
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to clear context: {e}")
            return False
    
    # ============================================
    # Agent State Management
    # ============================================
    
    def set_agent_state(
        self,
        user_id: str,
        session_id: str,
        agent_name: str,
        state: Dict[str, Any]
    ) -> bool:
        """
        Save agent state
        
        Args:
            user_id: User ID
            session_id: Chat session ID
            agent_name: Agent identifier
            state: Agent state dict
        
        Returns:
            bool: Success status
        """
        return self.set_context(
            user_id,
            session_id,
            f"agent_state:{agent_name}",
            state
        )
    
    def get_agent_state(
        self,
        user_id: str,
        session_id: str,
        agent_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get agent state"""
        return self.get_context(
            user_id,
            session_id,
            f"agent_state:{agent_name}"
        )


# Global singleton
memory_manager = MemoryManager()
