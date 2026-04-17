"""
Memory Manager - MongoDB-based conversation memory
Manages chat history, context, and agent state without Redis.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4
import logging

from pymongo import ASCENDING, DESCENDING, ReturnDocument

from core.config import settings

logger = logging.getLogger(__name__)


class MemoryManager:
    """Mongo-backed memory manager for multi-agent conversations."""

    def __init__(self):
        self.client = None
        self.db = None
        self.enabled = False
        self._indexes_ready = False

    def connect(self):
        """Connect to MongoDB."""
        try:
            from pymongo import MongoClient

            self.client = MongoClient(
                settings.MONGODB_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
                maxPoolSize=100,
                minPoolSize=5,
            )
            self.client.admin.command("ping")
            self.db = self.client[settings.MONGODB_DB_NAME]
            self.enabled = True
            self._ensure_indexes()
            logger.info("[OK] Connected to MongoDB conversation memory")
        except Exception as e:
            logger.warning(f"[WARN] MongoDB memory connection failed: {e}. Memory features disabled.")
            self.enabled = False

    def disconnect(self):
        """Disconnect from MongoDB."""
        if self.client:
            self.client.close()
            logger.info("[OK] Disconnected from MongoDB memory")
        self.client = None
        self.db = None

    def _ensure_indexes(self):
        if not self.enabled or self._indexes_ready:
            return

        conversations = self.db["conversations"]
        messages = self.db["messages"]
        summaries = self.db["conversation_summaries"]
        refs = self.db["message_source_refs"]
        state = self.db["conversation_state"]

        conversations.create_index([("conversation_id", ASCENDING)], unique=True)
        conversations.create_index([("user_id", ASCENDING), ("last_message_at", DESCENDING)])

        messages.create_index([("message_id", ASCENDING)], unique=True)
        messages.create_index(
            [("conversation_id", ASCENDING), ("branch_id", ASCENDING), ("sequence_no", ASCENDING)],
            unique=True,
        )
        messages.create_index([("conversation_id", ASCENDING), ("created_at", DESCENDING)])

        summaries.create_index([("conversation_id", ASCENDING), ("version", ASCENDING)], unique=True)
        summaries.create_index([("conversation_id", ASCENDING), ("status", ASCENDING)])

        refs.create_index(
            [("message_id", ASCENDING), ("source_id", ASCENDING), ("ref_type", ASCENDING)],
            unique=True,
        )
        refs.create_index([("conversation_id", ASCENDING), ("created_at", DESCENDING)])

        state.create_index([("conversation_id", ASCENDING)], unique=True)
        state.create_index([("user_id", ASCENDING), ("updated_at", DESCENDING)])

        self._indexes_ready = True

    def _next_sequence(self, user_id: str, session_id: str) -> int:
        now = datetime.utcnow()
        state = self.db["conversation_state"].find_one_and_update(
            {"conversation_id": session_id},
            {
                "$setOnInsert": {
                    "conversation_id": session_id,
                    "user_id": user_id,
                    "active_source_ids": [],
                    "last_resolved_source_ids": [],
                    "context": {},
                    "agent_states": {},
                    "created_at": now,
                },
                "$inc": {"last_message_sequence": 1},
                "$set": {"updated_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(state.get("last_message_sequence", 1))

    def _ensure_conversation(self, user_id: str, session_id: str):
        now = datetime.utcnow()
        self.db["conversations"].update_one(
            {"conversation_id": session_id},
            {
                "$setOnInsert": {
                    "conversation_id": session_id,
                    "user_id": user_id,
                    "title": "New Chat",
                    "session_type": "general",
                    "status": "active",
                    "created_at": now,
                    "message_count": 0,
                    "current_branch_id": "main",
                },
                "$set": {
                    "updated_at": now,
                    "last_message_at": now,
                },
            },
            upsert=True,
        )

    # ============================================
    # Chat History Management
    # ============================================

    def add_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> bool:
        if not self.enabled:
            return False

        try:
            self._ensure_conversation(user_id=user_id, session_id=session_id)
            sequence_no = self._next_sequence(user_id=user_id, session_id=session_id)
            now = datetime.utcnow()

            message_doc = {
                "message_id": str(uuid4()),
                "conversation_id": session_id,
                "user_id": user_id,
                "role": role,
                "sequence_no": sequence_no,
                "branch_id": "main",
                "parent_message_id": None,
                "content_text": content,
                "retrieved_chunk_ids": [],
                "llm_usage": {},
                "model_info": {},
                "trace_id": (metadata or {}).get("trace_id"),
                "metadata": metadata or {},
                "created_at": now,
                "edited_at": None,
                "deleted_at": None,
                "purge_after_at": None,
            }
            self.db["messages"].insert_one(message_doc)

            self.db["conversations"].update_one(
                {"conversation_id": session_id},
                {
                    "$inc": {"message_count": 1},
                    "$set": {
                        "updated_at": now,
                        "last_message_at": now,
                    },
                },
            )
            return True
        except Exception as e:
            logger.error(f"[ERR] Failed to add message: {e}")
            return False

    def get_chat_history(
        self,
        user_id: str,
        session_id: str,
        limit: int = 12,
    ) -> List[Dict]:
        if not self.enabled:
            return []

        try:
            cursor = (
                self.db["messages"]
                .find(
                    {
                        "conversation_id": session_id,
                        "user_id": user_id,
                        "deleted_at": None,
                    },
                    projection={
                        "_id": 0,
                        "role": 1,
                        "content_text": 1,
                        "created_at": 1,
                        "metadata": 1,
                    },
                )
                .sort("sequence_no", DESCENDING)
                .limit(limit)
            )
            rows = list(cursor)
            rows.reverse()
            return [
                {
                    "role": row.get("role"),
                    "content": row.get("content_text", ""),
                    "timestamp": row.get("created_at"),
                    "metadata": row.get("metadata", {}),
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"[ERR] Failed to get chat history: {e}")
            return []

    def get_last_message(
        self,
        user_id: str,
        session_id: str,
        role: Optional[str] = None,
    ) -> Optional[Dict]:
        history = self.get_chat_history(user_id=user_id, session_id=session_id, limit=20)
        if role:
            filtered = [msg for msg in history if msg.get("role") == role]
            return filtered[-1] if filtered else None
        return history[-1] if history else None

    def clear_chat_history(
        self,
        user_id: str,
        session_id: str,
    ) -> bool:
        if not self.enabled:
            return False

        try:
            now = datetime.utcnow()
            self.db["messages"].update_many(
                {
                    "conversation_id": session_id,
                    "user_id": user_id,
                    "deleted_at": None,
                },
                {"$set": {"deleted_at": now}},
            )
            return True
        except Exception as e:
            logger.error(f"[ERR] Failed to clear chat history: {e}")
            return False

    # ============================================
    # Context Management
    # ============================================

    def set_context(
        self,
        user_id: str,
        session_id: str,
        context_key: str,
        context_value: Any,
    ) -> bool:
        if not self.enabled:
            return False

        try:
            now = datetime.utcnow()
            self.db["conversation_state"].update_one(
                {"conversation_id": session_id},
                {
                    "$setOnInsert": {
                        "conversation_id": session_id,
                        "user_id": user_id,
                        "created_at": now,
                    },
                    "$set": {
                        f"context.{context_key}": context_value,
                        "updated_at": now,
                    },
                },
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error(f"[ERR] Failed to set context: {e}")
            return False

    def get_context(
        self,
        user_id: str,
        session_id: str,
        context_key: str,
    ) -> Optional[Any]:
        if not self.enabled:
            return None

        try:
            state = self.db["conversation_state"].find_one(
                {
                    "conversation_id": session_id,
                    "user_id": user_id,
                },
                projection={f"context.{context_key}": 1},
            )
            if not state:
                return None
            return ((state.get("context") or {}).get(context_key))
        except Exception as e:
            logger.error(f"[ERR] Failed to get context: {e}")
            return None

    def get_all_context(
        self,
        user_id: str,
        session_id: str,
    ) -> Dict[str, Any]:
        if not self.enabled:
            return {}

        try:
            state = self.db["conversation_state"].find_one(
                {
                    "conversation_id": session_id,
                    "user_id": user_id,
                },
                projection={"context": 1},
            )
            return (state or {}).get("context") or {}
        except Exception as e:
            logger.error(f"[ERR] Failed to get all context: {e}")
            return {}

    def clear_context(
        self,
        user_id: str,
        session_id: str,
    ) -> bool:
        if not self.enabled:
            return False

        try:
            self.db["conversation_state"].update_one(
                {
                    "conversation_id": session_id,
                    "user_id": user_id,
                },
                {"$set": {"context": {}, "updated_at": datetime.utcnow()}},
            )
            return True
        except Exception as e:
            logger.error(f"[ERR] Failed to clear context: {e}")
            return False

    # ============================================
    # Agent State Management
    # ============================================

    def set_agent_state(
        self,
        user_id: str,
        session_id: str,
        agent_name: str,
        state: Dict[str, Any],
    ) -> bool:
        if not self.enabled:
            return False

        try:
            now = datetime.utcnow()
            self.db["conversation_state"].update_one(
                {"conversation_id": session_id},
                {
                    "$setOnInsert": {
                        "conversation_id": session_id,
                        "user_id": user_id,
                        "created_at": now,
                    },
                    "$set": {
                        f"agent_states.{agent_name}": state,
                        "updated_at": now,
                    },
                },
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error(f"[ERR] Failed to set agent state: {e}")
            return False

    def get_agent_state(
        self,
        user_id: str,
        session_id: str,
        agent_name: str,
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None

        try:
            state = self.db["conversation_state"].find_one(
                {
                    "conversation_id": session_id,
                    "user_id": user_id,
                },
                projection={f"agent_states.{agent_name}": 1},
            )
            if not state:
                return None
            return ((state.get("agent_states") or {}).get(agent_name))
        except Exception as e:
            logger.error(f"[ERR] Failed to get agent state: {e}")
            return None


memory_manager = MemoryManager()
