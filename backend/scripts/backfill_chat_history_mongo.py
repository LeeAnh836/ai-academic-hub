"""
One-time backfill script: PostgreSQL chat tables -> Mongo chat history collections.

Usage:
    python scripts/backfill_chat_history_mongo.py
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from core.databases import SessionLocal
from core.mongo import mongo_chat_client
from models.chat import ChatSession, ChatMessage
from services.chat_history_service import chat_history_service


def run_backfill(db: Session):
    sessions = db.query(ChatSession).all()
    print(f"Found {len(sessions)} sessions to backfill")

    for session in sessions:
        conversation_id = str(session.id)
        user_id = str(session.user_id)

        chat_history_service.ensure_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            title=session.title,
            session_type=session.session_type,
        )

        pg_messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )

        for message in pg_messages:
            chat_history_service.append_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role=message.role,
                content_text=message.content,
                message_id=str(message.id),
                retrieved_chunk_ids=[str(chunk_id) for chunk_id in (message.retrieved_chunks or [])],
                llm_usage={
                    "token_total": int(message.total_tokens or 0),
                },
            )

        chat_history_service.upsert_summary_if_needed(
            conversation_id=conversation_id,
            user_id=user_id,
            recent_window_messages=12,
        )

    print("Backfill completed")


def main():
    mongo_chat_client.enabled = True
    import asyncio

    async def _run():
        await mongo_chat_client.connect()
        chat_history_service.ensure_indexes()

    asyncio.run(_run())

    db = SessionLocal()
    try:
        run_backfill(db)
    finally:
        db.close()

    async def _close():
        await mongo_chat_client.disconnect()

    asyncio.run(_close())


if __name__ == "__main__":
    main()
