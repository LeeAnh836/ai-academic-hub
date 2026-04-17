"""
Mongo-backed chat history service.

This service stores and retrieves conversation history, source metadata links,
and lightweight summaries. It is designed to be the source-of-truth for chat
history while allowing existing PostgreSQL APIs to remain compatible.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from sqlalchemy.orm import Session

from core.mongo import mongo_chat_client
from models.documents import Document


class ChatHistoryService:
    def __init__(self):
        self._indexes_ready = False

    @property
    def enabled(self) -> bool:
        return bool(mongo_chat_client.enabled and mongo_chat_client.get_db() is not None)

    def _db(self):
        return mongo_chat_client.get_db()

    def _col(self, name: str):
        db = self._db()
        if db is None:
            raise RuntimeError("Mongo chat history is not available")
        return db[name]

    def ensure_indexes(self):
        if not self.enabled or self._indexes_ready:
            return

        conversations = self._col("conversations")
        messages = self._col("messages")
        knowledge_sources = self._col("knowledge_sources")
        message_source_refs = self._col("message_source_refs")
        conversation_summaries = self._col("conversation_summaries")
        conversation_state = self._col("conversation_state")

        conversations.create_index([("conversation_id", ASCENDING)], unique=True)
        conversations.create_index([("user_id", ASCENDING), ("last_message_at", DESCENDING)])
        conversations.create_index([("status", ASCENDING), ("updated_at", DESCENDING)])
        conversations.create_index([("purge_after_at", ASCENDING)], expireAfterSeconds=0)

        messages.create_index([("message_id", ASCENDING)], unique=True)
        messages.create_index(
            [("conversation_id", ASCENDING), ("branch_id", ASCENDING), ("sequence_no", ASCENDING)],
            unique=True,
        )
        messages.create_index([("conversation_id", ASCENDING), ("created_at", DESCENDING)])
        messages.create_index([("trace_id", ASCENDING)])
        messages.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        messages.create_index([("purge_after_at", ASCENDING)], expireAfterSeconds=0)

        knowledge_sources.create_index([("source_id", ASCENDING)], unique=True)
        knowledge_sources.create_index([("owner_user_id", ASCENDING), ("updated_at", DESCENDING)])
        knowledge_sources.create_index([("canonical_document_id", ASCENDING)])
        knowledge_sources.create_index([("postgres_document_id", ASCENDING)])
        knowledge_sources.create_index([("ingestion_status", ASCENDING)])
        knowledge_sources.create_index([("checksum_sha256", ASCENDING)])
        knowledge_sources.create_index([("purge_after_at", ASCENDING)], expireAfterSeconds=0)

        message_source_refs.create_index([("ref_id", ASCENDING)], unique=True)
        message_source_refs.create_index(
            [("message_id", ASCENDING), ("source_id", ASCENDING), ("ref_type", ASCENDING)],
            unique=True,
        )
        message_source_refs.create_index([("conversation_id", ASCENDING), ("created_at", DESCENDING)])
        message_source_refs.create_index([("conversation_id", ASCENDING), ("source_id", ASCENDING), ("created_at", DESCENDING)])
        message_source_refs.create_index([("message_id", ASCENDING)])

        conversation_summaries.create_index([("conversation_id", ASCENDING), ("version", ASCENDING)], unique=True)
        conversation_summaries.create_index([("conversation_id", ASCENDING), ("status", ASCENDING)])
        conversation_summaries.create_index([("conversation_id", ASCENDING), ("created_at", DESCENDING)])
        conversation_summaries.create_index([("conversation_id", ASCENDING), ("covered_until_sequence", DESCENDING)])
        conversation_summaries.create_index([("purge_after_at", ASCENDING)], expireAfterSeconds=0)

        conversation_state.create_index([("conversation_id", ASCENDING)], unique=True)
        conversation_state.create_index([("user_id", ASCENDING), ("updated_at", DESCENDING)])

        self._indexes_ready = True

    def ensure_conversation(
        self,
        conversation_id: str,
        user_id: str,
        title: Optional[str] = None,
        session_type: str = "general",
    ):
        if not self.enabled:
            return
        self.ensure_indexes()

        now = datetime.utcnow()
        self._col("conversations").update_one(
            {"conversation_id": conversation_id},
            {
                "$setOnInsert": {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "title": title or "New Chat",
                    "session_type": session_type,
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

        self._col("conversation_state").update_one(
            {"conversation_id": conversation_id},
            {
                "$setOnInsert": {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "current_summary_version": None,
                    "summary_covered_until_sequence": 0,
                    "active_source_ids": [],
                    "pinned_source_ids": [],
                    "last_resolved_source_ids": [],
                    "last_message_sequence": 0,
                    "context_policy": {
                        "recent_turns": 6,
                        "max_prompt_tokens": 12000,
                        "max_chunk_count": 8,
                    },
                    "created_at": now,
                },
                "$set": {
                    "updated_at": now,
                },
            },
            upsert=True,
        )

    def list_conversations(self, user_id: str, skip: int = 0, limit: int = 20) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        cursor = (
            self._col("conversations")
            .find({"user_id": user_id, "status": {"$ne": "deleted"}})
            .sort("last_message_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        return list(cursor)

    def _next_sequence(self, conversation_id: str, user_id: str) -> int:
        now = datetime.utcnow()
        state = self._col("conversation_state").find_one_and_update(
            {"conversation_id": conversation_id},
            {
                "$setOnInsert": {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "active_source_ids": [],
                    "pinned_source_ids": [],
                    "last_resolved_source_ids": [],
                    "current_summary_version": None,
                    "summary_covered_until_sequence": 0,
                    "context_policy": {
                        "recent_turns": 6,
                        "max_prompt_tokens": 12000,
                        "max_chunk_count": 8,
                    },
                    "created_at": now,
                },
                "$inc": {"last_message_sequence": 1},
                "$set": {"updated_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(state.get("last_message_sequence", 1))

    def append_message(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        content_text: str,
        message_id: Optional[str] = None,
        source_ids: Optional[List[str]] = None,
        ref_type: str = "inferred_active",
        trace_id: Optional[str] = None,
        llm_usage: Optional[Dict[str, Any]] = None,
        model_info: Optional[Dict[str, Any]] = None,
        retrieved_chunk_ids: Optional[List[str]] = None,
        branch_id: str = "main",
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None

        self.ensure_indexes()
        message_id = message_id or str(uuid4())
        messages = self._col("messages")

        existing = messages.find_one({"message_id": message_id})
        if existing:
            return existing

        sequence_no = self._next_sequence(conversation_id=conversation_id, user_id=user_id)
        now = datetime.utcnow()
        doc = {
            "message_id": message_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": role,
            "sequence_no": sequence_no,
            "branch_id": branch_id,
            "parent_message_id": None,
            "content_text": content_text,
            "retrieved_chunk_ids": retrieved_chunk_ids or [],
            "llm_usage": llm_usage or {},
            "model_info": model_info or {},
            "trace_id": trace_id,
            "created_at": now,
            "edited_at": None,
            "deleted_at": None,
            "purge_after_at": None,
        }
        messages.insert_one(doc)

        self._col("conversations").update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "updated_at": now,
                    "last_message_at": now,
                    "last_trace_id": trace_id,
                },
                "$inc": {"message_count": 1},
            },
            upsert=True,
        )

        if source_ids:
            self.add_message_source_refs(
                message_id=message_id,
                conversation_id=conversation_id,
                source_ids=source_ids,
                ref_type=ref_type,
                trace_id=trace_id,
            )
            self.set_active_source_ids(
                conversation_id=conversation_id,
                user_id=user_id,
                source_ids=source_ids,
                trace_id=trace_id,
            )

        return doc

    def add_message_source_refs(
        self,
        message_id: str,
        conversation_id: str,
        source_ids: List[str],
        ref_type: str,
        trace_id: Optional[str] = None,
        chunk_ids: Optional[List[str]] = None,
        confidence: float = 0.9,
    ):
        if not self.enabled or not source_ids:
            return

        now = datetime.utcnow()
        refs = self._col("message_source_refs")

        deduped: List[str] = []
        seen = set()
        for source_id in source_ids:
            if source_id and source_id not in seen:
                seen.add(source_id)
                deduped.append(source_id)

        for source_id in deduped:
            refs.update_one(
                {
                    "message_id": message_id,
                    "source_id": source_id,
                    "ref_type": ref_type,
                },
                {
                    "$setOnInsert": {
                        "ref_id": str(uuid4()),
                        "conversation_id": conversation_id,
                        "message_id": message_id,
                        "source_id": source_id,
                        "ref_type": ref_type,
                        "confidence": confidence,
                        "weight": 1.0,
                        "resolver_reason": ref_type,
                        "created_at": now,
                    },
                    "$set": {
                        "trace_id": trace_id,
                        "chunk_ids": chunk_ids or [],
                    },
                },
                upsert=True,
            )

    def set_active_source_ids(
        self,
        conversation_id: str,
        user_id: str,
        source_ids: List[str],
        trace_id: Optional[str] = None,
    ):
        if not self.enabled:
            return

        now = datetime.utcnow()
        deduped = []
        seen = set()
        for source_id in source_ids:
            if source_id and source_id not in seen:
                seen.add(source_id)
                deduped.append(source_id)

        self._col("conversation_state").update_one(
            {"conversation_id": conversation_id},
            {
                "$setOnInsert": {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "last_message_sequence": 0,
                    "created_at": now,
                },
                "$set": {
                    "active_source_ids": deduped,
                    "last_resolved_source_ids": deduped,
                    "updated_at": now,
                    "trace_id": trace_id,
                },
            },
            upsert=True,
        )

    def resolve_source_ids(
        self,
        conversation_id: str,
        user_id: str,
        explicit_source_ids: Optional[List[str]] = None,
    ) -> List[str]:
        if not self.enabled:
            return []

        if explicit_source_ids is not None:
            deduped = []
            seen = set()
            for source_id in explicit_source_ids:
                if source_id and source_id not in seen:
                    seen.add(source_id)
                    deduped.append(source_id)
            self.set_active_source_ids(
                conversation_id=conversation_id,
                user_id=user_id,
                source_ids=deduped,
            )
            return deduped

        state = self._col("conversation_state").find_one(
            {"conversation_id": conversation_id},
            projection={"active_source_ids": 1},
        )
        active = (state or {}).get("active_source_ids") or []
        if active:
            return active

        recent_refs = (
            self._col("message_source_refs")
            .find({"conversation_id": conversation_id}, projection={"source_id": 1})
            .sort("created_at", DESCENDING)
            .limit(20)
        )

        deduped = []
        seen = set()
        for ref in recent_refs:
            source_id = ref.get("source_id")
            if source_id and source_id not in seen:
                seen.add(source_id)
                deduped.append(source_id)

        if deduped:
            self.set_active_source_ids(
                conversation_id=conversation_id,
                user_id=user_id,
                source_ids=deduped,
            )

        return deduped

    def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = 12,
    ) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []

        cursor = (
            self._col("messages")
            .find({"conversation_id": conversation_id, "deleted_at": None})
            .sort("sequence_no", DESCENDING)
            .limit(limit)
        )
        items = list(cursor)
        items.reverse()
        return items

    def get_session_messages(
        self,
        conversation_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []

        cursor = (
            self._col("messages")
            .find({"conversation_id": conversation_id, "deleted_at": None})
            .sort("sequence_no", ASCENDING)
            .skip(skip)
            .limit(limit)
        )
        return list(cursor)

    def get_message_refs_map(self, conversation_id: str, message_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        if not self.enabled or not message_ids:
            return {}

        refs = (
            self._col("message_source_refs")
            .find({"conversation_id": conversation_id, "message_id": {"$in": message_ids}})
            .sort("created_at", ASCENDING)
        )
        out: Dict[str, List[Dict[str, Any]]] = {}
        for ref in refs:
            out.setdefault(ref["message_id"], []).append(ref)
        return out

    def get_conversation_source_catalog(
        self,
        conversation_id: str,
        user_id: str,
        max_recent_refs: int = 200,
        max_sources: int = 80,
    ) -> List[Dict[str, Any]]:
        """Return ordered source metadata candidates relevant to a conversation."""
        if not self.enabled:
            return []

        ordered_source_ids: List[str] = []
        seen = set()

        state = self._col("conversation_state").find_one(
            {"conversation_id": conversation_id},
            projection={
                "active_source_ids": 1,
                "last_resolved_source_ids": 1,
                "pinned_source_ids": 1,
            },
        ) or {}

        for field_name in ["active_source_ids", "last_resolved_source_ids", "pinned_source_ids"]:
            for source_id in state.get(field_name) or []:
                normalized = str(source_id).strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    ordered_source_ids.append(normalized)

        recent_refs = (
            self._col("message_source_refs")
            .find({"conversation_id": conversation_id}, projection={"source_id": 1})
            .sort("created_at", DESCENDING)
            .limit(max_recent_refs)
        )
        for ref in recent_refs:
            source_id = str(ref.get("source_id") or "").strip()
            if source_id and source_id not in seen:
                seen.add(source_id)
                ordered_source_ids.append(source_id)

        if ordered_source_ids:
            return self.get_source_metadata(ordered_source_ids[:max_sources])

        # Fallback: use latest user-owned sources when conversation has no refs yet.
        cursor = self._col("knowledge_sources").find(
            {"owner_user_id": str(user_id)},
            projection={
                "_id": 0,
                "source_id": 1,
                "source_type": 1,
                "file_name": 1,
                "mime_type": 1,
                "size_bytes": 1,
                "canonical_document_id": 1,
                "postgres_document_id": 1,
                "metadata": 1,
                "last_used_at": 1,
            },
        ).sort("last_used_at", DESCENDING).limit(max_sources)

        return list(cursor)

    def upsert_sources_from_document_ids(
        self,
        db: Session,
        user_id: str,
        document_ids: List[str],
    ) -> List[str]:
        if not self.enabled or not document_ids:
            return []

        now = datetime.utcnow()
        sources = self._col("knowledge_sources")

        valid_uuid_ids = []
        for document_id in document_ids:
            try:
                valid_uuid_ids.append(UUID(str(document_id)))
            except Exception:
                continue

        rows = []
        if valid_uuid_ids:
            rows = (
                db.query(Document)
                .filter(Document.user_id == user_id)
                .filter(Document.id.in_(valid_uuid_ids))
                .all()
            )

        source_ids: List[str] = []
        seen = set()

        for row in rows:
            canonical_id = str(row.canonical_document_id or row.id)
            if canonical_id in seen:
                continue
            seen.add(canonical_id)
            source_ids.append(canonical_id)

            sources.update_one(
                {"source_id": canonical_id},
                {
                    "$setOnInsert": {
                        "source_id": canonical_id,
                        "created_at": now,
                        "source_type": "document",
                        "owner_user_id": str(user_id),
                    },
                    "$set": {
                        "updated_at": now,
                        "postgres_document_id": str(row.id),
                        "canonical_document_id": canonical_id,
                        "file_name": row.file_name,
                        "mime_type": row.file_type,
                        "size_bytes": int(row.file_size or 0),
                        "checksum_sha256": row.content_hash,
                        "ingestion_status": "ready" if row.is_processed else row.processing_status,
                        "qdrant_collection": "jvb_embeddings",
                        "qdrant_filter_document_ids": [canonical_id],
                        "metadata": {
                            "title": row.title,
                            "tags": row.tags or [],
                            "category": row.category,
                        },
                        "last_used_at": now,
                    },
                },
                upsert=True,
            )

        # Keep unknown IDs as lightweight placeholders.
        unknown_ids = [doc_id for doc_id in document_ids if str(doc_id) not in seen]
        for unknown_id in unknown_ids:
            source_id = str(unknown_id)
            if source_id in seen:
                continue
            seen.add(source_id)
            source_ids.append(source_id)
            sources.update_one(
                {"source_id": source_id},
                {
                    "$setOnInsert": {
                        "source_id": source_id,
                        "created_at": now,
                        "source_type": "document",
                        "owner_user_id": str(user_id),
                    },
                    "$set": {
                        "updated_at": now,
                        "postgres_document_id": source_id,
                        "canonical_document_id": source_id,
                        "file_name": source_id,
                        "mime_type": None,
                        "size_bytes": 0,
                        "checksum_sha256": None,
                        "ingestion_status": "unknown",
                        "qdrant_collection": "jvb_embeddings",
                        "qdrant_filter_document_ids": [source_id],
                        "metadata": {
                            "title": source_id,
                            "tags": [],
                            "category": None,
                        },
                        "last_used_at": now,
                    },
                },
                upsert=True,
            )

        return source_ids

    def get_source_metadata(self, source_ids: List[str]) -> List[Dict[str, Any]]:
        if not self.enabled or not source_ids:
            return []

        cursor = self._col("knowledge_sources").find(
            {"source_id": {"$in": source_ids}},
            projection={
                "_id": 0,
                "source_id": 1,
                "source_type": 1,
                "file_name": 1,
                "mime_type": 1,
                "size_bytes": 1,
                "canonical_document_id": 1,
                "postgres_document_id": 1,
                "metadata": 1,
                "last_used_at": 1,
            },
        )
        items = list(cursor)

        # Preserve requested order.
        mapping = {item["source_id"]: item for item in items}
        return [mapping[sid] for sid in source_ids if sid in mapping]

    def touch_sources(self, source_ids: List[str]):
        if not self.enabled or not source_ids:
            return
        self._col("knowledge_sources").update_many(
            {"source_id": {"$in": source_ids}},
            {"$set": {"last_used_at": datetime.utcnow()}},
        )

    def get_latest_summary(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None

        return self._col("conversation_summaries").find_one(
            {"conversation_id": conversation_id, "status": "active"},
            sort=[("version", DESCENDING)],
        )

    def upsert_summary_if_needed(
        self,
        conversation_id: str,
        user_id: str,
        recent_window_messages: int = 12,
    ) -> Optional[str]:
        if not self.enabled:
            return None

        total_messages = self._col("messages").count_documents(
            {"conversation_id": conversation_id, "deleted_at": None}
        )
        if total_messages <= recent_window_messages:
            active = self.get_latest_summary(conversation_id)
            return active.get("summary_text") if active else None

        older_messages = list(
            self._col("messages")
            .find({"conversation_id": conversation_id, "deleted_at": None})
            .sort("sequence_no", DESCENDING)
            .skip(recent_window_messages)
            .limit(48)
        )
        if not older_messages:
            return None

        older_messages.reverse()

        lines: List[str] = []
        for msg in older_messages:
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = (msg.get("content_text") or "").strip().replace("\n", " ")
            if len(content) > 180:
                content = content[:180] + "..."
            if content:
                lines.append(f"{role}: {content}")

        if not lines:
            return None

        summary_text = " | ".join(lines)
        if len(summary_text) > 4000:
            summary_text = summary_text[:4000] + "..."

        summaries = self._col("conversation_summaries")
        now = datetime.utcnow()
        previous = summaries.find_one(
            {"conversation_id": conversation_id, "status": "active"},
            sort=[("version", DESCENDING)],
        )
        if previous and previous.get("summary_text") == summary_text:
            return summary_text

        new_version = int(previous.get("version", 0) + 1) if previous else 1
        covered_until_sequence = int(older_messages[-1].get("sequence_no", 0))

        summaries.update_many(
            {"conversation_id": conversation_id, "status": "active"},
            {
                "$set": {
                    "status": "superseded",
                    "superseded_at": now,
                }
            },
        )

        summaries.insert_one(
            {
                "summary_id": str(uuid4()),
                "conversation_id": conversation_id,
                "version": new_version,
                "status": "active",
                "covered_until_sequence": covered_until_sequence,
                "summary_text": summary_text,
                "key_facts": [],
                "active_source_ids": [],
                "unresolved_items": [],
                "model_info": {
                    "provider": "heuristic",
                    "model_name": "rule-based-summary",
                },
                "llm_usage": {
                    "token_in": 0,
                    "token_out": 0,
                    "token_total": 0,
                },
                "trace_id": None,
                "created_at": now,
                "superseded_at": None,
                "purge_after_at": None,
            }
        )

        self._col("conversation_state").update_one(
            {"conversation_id": conversation_id},
            {
                "$setOnInsert": {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "created_at": now,
                },
                "$set": {
                    "current_summary_version": new_version,
                    "summary_covered_until_sequence": covered_until_sequence,
                    "updated_at": now,
                },
            },
            upsert=True,
        )

        return summary_text

    def build_context_bundle(
        self,
        conversation_id: str,
        user_id: str,
        explicit_source_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "chat_history": [],
                "conversation_summary": None,
                "source_ids": [],
                "source_metadata": [],
            }

        source_ids = self.resolve_source_ids(
            conversation_id=conversation_id,
            user_id=user_id,
            explicit_source_ids=explicit_source_ids,
        )
        self.touch_sources(source_ids)

        summary_text = self.upsert_summary_if_needed(
            conversation_id=conversation_id,
            user_id=user_id,
            recent_window_messages=12,
        )
        recent_messages = self.get_recent_messages(conversation_id=conversation_id, limit=12)

        return {
            "chat_history": [
                {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content_text", ""),
                }
                for msg in recent_messages
            ],
            "conversation_summary": summary_text,
            "source_ids": source_ids,
            "source_metadata": self.get_source_metadata(source_ids),
        }

    def clear_conversation(self, conversation_id: str):
        if not self.enabled:
            return

        now = datetime.utcnow()
        purge_after = now + timedelta(days=30)

        self._col("conversations").update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "status": "deleted",
                    "updated_at": now,
                    "purge_after_at": purge_after,
                }
            },
        )
        self._col("messages").update_many(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "deleted_at": now,
                    "purge_after_at": purge_after,
                }
            },
        )
        self._col("conversation_summaries").update_many(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "purge_after_at": purge_after,
                }
            },
        )


chat_history_service = ChatHistoryService()
