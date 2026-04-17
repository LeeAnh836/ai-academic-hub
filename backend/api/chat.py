"""
Chat routes - Chat sessions, messages
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import Any, Dict, List
from uuid import UUID, uuid4
import re

from core.databases import get_db
from api.dependencies import get_current_user, CurrentUser
from services.chat_service import chat_service
from services.chat_history_service import chat_history_service
from schemas.chat import (
    ChatSessionResponse, ChatSessionCreateRequest, ChatMessageResponse,
    ChatMessageCreateRequest, MessageFeedbackRequest, ChatSessionDetailResponse,
    AIUsageResponse, ChatAskRequest, ChatAskResponse, ContextChunkResponse,
    ChatSessionUpdateTitleRequest
)
from models.users import User
from models.chat import ChatSession, ChatMessage, MessageFeedback, AIUsageHistory
from models.documents import Document
import httpx
import time
from core.config import settings

router = APIRouter(
    prefix="/api/chat", 
    tags=["chat"],
    dependencies=[Depends(get_current_user)]  # Apply authentication to all endpoints
)


FILE_MENTION_PATTERN = re.compile(
    r"(?<![\w/\\])([A-Za-z0-9][A-Za-z0-9._-]{0,120}\.[A-Za-z0-9]{1,12})(?![\w])",
    re.IGNORECASE,
)
SOURCE_ID_PREFIX_PATTERN = re.compile(r"\bid\s*:\s*([0-9a-fA-F]{8})\b", re.IGNORECASE)


def _resolve_canonical_document_ids(db: Session, user_id: UUID, document_ids: List[str]) -> List[str]:
    """Map user document IDs to canonical IDs used for vector retrieval."""
    if not document_ids:
        return []

    out: List[str] = []
    seen = set()

    for raw_id in document_ids:
        doc = db.query(Document).filter(
            Document.id == raw_id,
            Document.user_id == user_id
        ).first()
        mapped = str(doc.canonical_document_id or doc.id) if doc else str(raw_id)
        if mapped not in seen:
            seen.add(mapped)
            out.append(mapped)

    return out


def _resolve_trace_id(request: Request) -> str:
    incoming = request.headers.get("x-trace-id") or request.headers.get("x-request-id")
    if incoming and incoming.strip():
        return incoming.strip()
    return str(uuid4())


def _mongo_message_to_response(message: dict, session_id: UUID) -> dict:
    """Map Mongo message doc to API response shape."""
    retrieved_chunks = []
    for chunk_id in message.get("retrieved_chunk_ids", []):
        if not chunk_id:
            continue
        try:
            UUID(str(chunk_id))
            retrieved_chunks.append(str(chunk_id))
        except Exception:
            continue

    return {
        "id": message.get("message_id"),
        "session_id": str(session_id),
        "user_id": message.get("user_id"),
        "role": message.get("role"),
        "content": message.get("content_text", ""),
        "retrieved_chunks": retrieved_chunks,
        "total_tokens": int((message.get("llm_usage") or {}).get("token_total", 0)),
        "confidence_score": None,
        "created_at": message.get("created_at"),
    }


def _is_ambiguous_reference_query(query: str) -> bool:
    query_lower = (query or "").strip().lower()
    if not query_lower:
        return False

    deictic_markers = [
        "này", "nay", "đó", "do", "kia", "ở trên", "o tren",
        "this", "that", "above", "attached",
    ]
    object_markers = [
        "bài", "bai", "bài tập", "bai tap", "câu", "cau", "hình", "hinh", "ảnh", "anh",
        "file", "tài liệu", "tai lieu", "document", "image", "problem", "exercise",
    ]

    has_deictic = any(marker in query_lower for marker in deictic_markers)
    has_object = any(marker in query_lower for marker in object_markers)
    return has_deictic and has_object and len(query_lower.split()) <= 18


def _json_safe(value: Any) -> Any:
    """Convert nested values to JSON-serializable representation."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def _normalize_source_label(label: str) -> str:
    normalized = (label or "").strip().lower()
    if not normalized:
        return ""
    if "| id:" in normalized:
        normalized = normalized.split("| id:", 1)[0].strip()
    normalized = normalized.replace("\\", "/")
    return normalized.split("/")[-1].strip()


def _extract_file_mentions(query: str) -> List[str]:
    mentions: List[str] = []
    seen = set()
    for match in FILE_MENTION_PATTERN.finditer(query or ""):
        token = _normalize_source_label(match.group(1))
        if token and token not in seen:
            seen.add(token)
            mentions.append(token)
    return mentions


def _extract_source_id_prefixes(query: str) -> List[str]:
    prefixes: List[str] = []
    seen = set()
    for match in SOURCE_ID_PREFIX_PATTERN.finditer(query or ""):
        prefix = match.group(1).lower()
        if prefix and prefix not in seen:
            seen.add(prefix)
            prefixes.append(prefix)
    return prefixes


def _resolve_source_ids_from_query_mentions(
    query: str,
    source_catalog: List[Dict[str, Any]],
) -> List[str]:
    if not source_catalog:
        return []

    id_prefixes = _extract_source_id_prefixes(query)
    file_mentions = _extract_file_mentions(query)
    if not id_prefixes and not file_mentions:
        return []

    entries: List[Dict[str, Any]] = []
    for source in source_catalog:
        source_id = str(source.get("source_id") or "").strip()
        if not source_id:
            continue

        metadata = source.get("metadata") or {}
        names = set()
        for candidate in [source.get("file_name"), metadata.get("title")]:
            normalized = _normalize_source_label(str(candidate or ""))
            if normalized:
                names.add(normalized)

        entries.append({"source_id": source_id, "names": names})

    matched: List[str] = []
    seen = set()

    for prefix in id_prefixes:
        for entry in entries:
            source_id = entry["source_id"]
            if source_id.lower().startswith(prefix) and source_id not in seen:
                seen.add(source_id)
                matched.append(source_id)
                break

    for mention in file_mentions:
        for entry in entries:
            source_id = entry["source_id"]
            names = entry["names"]
            if source_id in seen:
                continue

            if mention in names:
                seen.add(source_id)
                matched.append(source_id)
                break

    return matched


def _source_display_name(source_meta: Dict[str, Any]) -> str:
    metadata = source_meta.get("metadata") or {}
    return (
        source_meta.get("file_name")
        or metadata.get("title")
        or source_meta.get("source_id")
        or "unknown"
    )


def _sanitize_source_refs(raw_refs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sanitized: List[Dict[str, Any]] = []
    for ref in raw_refs or []:
        source_id = str(ref.get("source_id") or "").strip()
        if not source_id:
            continue
        sanitized.append(
            {
                "source_id": source_id,
                "ref_type": str(ref.get("ref_type") or ""),
                "confidence": float(ref.get("confidence") or 0.0),
                "chunk_ids": [str(chunk_id) for chunk_id in (ref.get("chunk_ids") or []) if chunk_id],
                "trace_id": ref.get("trace_id"),
                "created_at": ref.get("created_at"),
            }
        )
    return _json_safe(sanitized)


def _build_message_persistence_payload(
    message_role: str,
    source_refs: List[Dict[str, Any]],
    source_catalog: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    attached_files: List[Dict[str, Any]] = []
    doc_map: List[Dict[str, str]] = []

    seen_attached = set()
    seen_doc_map = set()

    for ref in source_refs:
        source_id = str(ref.get("source_id") or "").strip()
        if not source_id:
            continue

        source_meta = source_catalog.get(source_id) or {"source_id": source_id}
        display_name = _source_display_name(source_meta)
        raw_file_name = display_name
        citation_label = f"{display_name} | id:{source_id[:8]}"

        if source_id not in seen_doc_map:
            seen_doc_map.add(source_id)
            doc_map.append(
                {
                    "file_name": citation_label,
                    "raw_file_name": raw_file_name,
                    "document_id": source_id,
                }
            )

        if message_role == "user" and ref.get("ref_type") == "explicit_attachment" and source_id not in seen_attached:
            seen_attached.add(source_id)
            attached_files.append(
                {
                    "document_id": source_id,
                    "name": display_name,
                    "size": int(source_meta.get("size_bytes") or 0),
                    "type": str(source_meta.get("mime_type") or ""),
                }
            )

    return {
        "attached_files": attached_files,
        "doc_map": doc_map,
    }


# ============================================
# List chat sessions
# ============================================
@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 10
):
    """
    Lấy danh sách chat sessions của user
    """
    sessions = chat_service.get_user_chat_sessions(
        user_id=str(current_user.id),
        db=db,
        skip=skip,
        limit=limit
    )
    
    return sessions


# ============================================
# Create chat session
# ============================================
@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    request: ChatSessionCreateRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Tạo chat session mới
    """
    new_session = chat_service.create_chat_session(
        user_id=str(current_user.id),
        title=request.title,
        session_type=request.session_type,
        context_documents=request.context_documents or [],
        model_name=request.model_name,
        db=db
    )

    if chat_history_service.enabled:
        chat_history_service.ensure_conversation(
            conversation_id=str(new_session.id),
            user_id=str(current_user.id),
            title=new_session.title,
            session_type=new_session.session_type,
        )
    
    return new_session


# ============================================
# Get chat session detail
# ============================================
@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_chat_session(
    session_id: UUID,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Lấy chi tiết chat session
    """
    session = chat_service.get_chat_session_by_id(
        session_id=session_id,
        user_id=str(current_user.id),
        db=db
    )
    
    return session


# ============================================
# Update session title
# ============================================
@router.patch("/sessions/{session_id}/title", response_model=ChatSessionResponse)
async def update_chat_session_title(
    session_id: UUID,
    request: ChatSessionUpdateTitleRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Cập nhật tiêu đề chat session
    """
    return chat_service.update_chat_session_title(
        session_id=session_id,
        user_id=str(current_user.id),
        title=request.title,
        db=db
    )


# ============================================
# Send chat message
# ============================================
@router.post("/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_chat_message(
    request: ChatMessageCreateRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Gửi tin nhắn trong chat session
    """
    # Kiểm tra session tồn tại và user có quyền
    session = db.query(ChatSession).filter(
        ChatSession.id == request.session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to send messages to this session"
        )
    
    # Tạo message
    new_message = ChatMessage(
        session_id=request.session_id,
        user_id=current_user.id,
        role="user",
        content=request.content,
        retrieved_chunks=request.retrieved_chunks or []
    )
    
    db.add(new_message)
    
    # Cập nhật message count
    session.message_count += 1
    
    db.commit()
    db.refresh(new_message)

    if chat_history_service.enabled:
        chat_history_service.ensure_conversation(
            conversation_id=str(request.session_id),
            user_id=str(current_user.id),
            title=session.title,
            session_type=session.session_type,
        )
        chat_history_service.append_message(
            conversation_id=str(request.session_id),
            user_id=str(current_user.id),
            role="user",
            content_text=request.content,
            message_id=str(new_message.id),
            retrieved_chunk_ids=[str(chunk_id) for chunk_id in (request.retrieved_chunks or [])],
        )
    
    return new_message


# ============================================
# Get session messages
# ============================================
@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_session_messages(
    session_id: UUID,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50
):
    """
    Lấy danh sách tin nhắn trong session
    """
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this session"
        )

    if chat_history_service.enabled:
        mongo_messages = chat_history_service.get_session_messages(
            conversation_id=str(session_id),
            skip=skip,
            limit=limit,
        )
        if mongo_messages:
            return [_mongo_message_to_response(message, session_id) for message in mongo_messages]
    
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).offset(skip).limit(limit).all()
    
    return messages


@router.get("/sessions/{session_id}/timeline")
async def get_session_timeline(
    session_id: UUID,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
):
    """Return message timeline with source references for UI/source resolution debugging."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this session",
        )

    if not chat_history_service.enabled:
        fallback_messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).offset(skip).limit(limit).all()
        return {
            "session_id": str(session_id),
            "source_catalog": {},
            "messages": [
                {
                    "message": ChatMessageResponse.model_validate(msg).model_dump(),
                    "source_refs": [],
                    "attached_files": [],
                    "doc_map": [],
                }
                for msg in fallback_messages
            ],
        }

    mongo_messages = chat_history_service.get_session_messages(
        conversation_id=str(session_id),
        skip=skip,
        limit=limit,
    )
    message_ids = [str(msg.get("message_id")) for msg in mongo_messages if msg.get("message_id")]
    refs_map = chat_history_service.get_message_refs_map(
        conversation_id=str(session_id),
        message_ids=message_ids,
    )

    source_ids: List[str] = []
    seen_source_ids = set()
    for refs in refs_map.values():
        for ref in refs:
            source_id = str(ref.get("source_id") or "").strip()
            if source_id and source_id not in seen_source_ids:
                seen_source_ids.add(source_id)
                source_ids.append(source_id)

    source_catalog_list = chat_history_service.get_source_metadata(source_ids)
    source_catalog: Dict[str, Dict[str, Any]] = {
        str(item.get("source_id")): _json_safe(item)
        for item in source_catalog_list
        if item.get("source_id")
    }

    timeline_messages = []
    for msg in mongo_messages:
        message_id = str(msg.get("message_id")) if msg.get("message_id") else ""
        source_refs = _sanitize_source_refs(refs_map.get(message_id, []))
        persistence_payload = _build_message_persistence_payload(
            message_role=str(msg.get("role") or ""),
            source_refs=source_refs,
            source_catalog=source_catalog,
        )
        timeline_messages.append(
            {
                "message": _mongo_message_to_response(msg, session_id),
                "source_refs": source_refs,
                "attached_files": persistence_payload["attached_files"],
                "doc_map": persistence_payload["doc_map"],
            }
        )

    return {
        "session_id": str(session_id),
        "source_catalog": source_catalog,
        "messages": timeline_messages,
    }


# ============================================
# Send feedback for message
# ============================================
@router.post("/messages/{message_id}/feedback")
async def send_message_feedback(
    message_id: UUID,
    request: MessageFeedbackRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Gửi feedback cho tin nhắn
    """
    message = db.query(ChatMessage).filter(
        ChatMessage.id == message_id
    ).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    if message.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to send feedback for this message"
        )
    
    # Kiểm tra feedback đã tồn tại
    feedback = db.query(MessageFeedback).filter(
        MessageFeedback.message_id == message_id
    ).first()
    
    if not feedback:
        feedback = MessageFeedback(message_id=message_id)
        db.add(feedback)
    
    # Cập nhật feedback
    if request.rating is not None:
        feedback.rating = request.rating
    if request.is_helpful is not None:
        feedback.is_helpful = request.is_helpful
    if request.comment is not None:
        feedback.comment = request.comment
    if request.feedback_type is not None:
        feedback.feedback_type = request.feedback_type
    
    db.commit()
    db.refresh(feedback)
    
    return {"message": "Feedback sent successfully"}


# ============================================
# Delete chat session
# ============================================
@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: UUID,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Xóa chat session
    """
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this session"
        )

    if chat_history_service.enabled:
        chat_history_service.clear_conversation(str(session_id))

    db.delete(session)
    db.commit()


# ============================================
# Ask AI in chat session (Integration Endpoint)
# ============================================
@router.post("/sessions/{session_id}/ask", response_model=ChatAskResponse)
async def ask_in_chat_session(
    session_id: UUID,
    request: ChatAskRequest,
    current_user: CurrentUser,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    Hỏi AI trong chat session - Tự động lưu messages và gọi AI Service
    
    Flow:
    1. Validate session & user permission
    2. Save user message to chat_messages
    3. Call AI Service internally
    4. Save AI response to chat_messages
    5. Update session stats
    6. Track usage to ai_usage_history
    7. Return complete conversation
    """
    start_time = time.time()
    trace_id = _resolve_trace_id(http_request)
    
    # 1. Validate session
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to use this session"
        )
    
    # 2. Save user message
    user_message = ChatMessage(
        session_id=session_id,
        user_id=current_user.id,
        role="user",
        content=request.question,
        retrieved_chunks=[],
        total_tokens=0
    )
    db.add(user_message)
    db.flush()  # Get ID without committing
    
    try:
        # 3. Call AI Service internally (Multi-Agent System)
        ai_service_url = f"{settings.AI_SERVICE_URL}/api/agent/query"
        
        # Prepare request for AI Service
        # Logic: 
        # - document_ids=[] → Direct chat (no RAG)
        # - document_ids=None → Use session's context_documents (no cross-session fallback)
        # - document_ids=[...] → Use specified documents AND persist to session
        if request.document_ids is not None:
            # User explicitly specified (including [])
            raw_doc_ids = [str(doc_id) for doc_id in request.document_ids] if request.document_ids else []
            doc_ids_to_use = _resolve_canonical_document_ids(db, current_user.id, raw_doc_ids) if raw_doc_ids else []
            # Persist non-empty doc lists to session so follow-up questions remember context
            if request.document_ids:
                session.context_documents = [str(doc_id) for doc_id in request.document_ids]
                db.flush()
        else:
            # Use session's persistent context (no global cross-session fallback)
            if session.context_documents:
                doc_ids_to_use = _resolve_canonical_document_ids(
                    db,
                    current_user.id,
                    [str(doc_id) for doc_id in session.context_documents],
                )
            else:
                doc_ids_to_use = None

        filename_mention_source_ids: List[str] = []
        if chat_history_service.enabled and request.document_ids is None:
            conversation_source_catalog = chat_history_service.get_conversation_source_catalog(
                conversation_id=str(session_id),
                user_id=str(current_user.id),
                max_recent_refs=300,
                max_sources=80,
            )
            filename_mention_source_ids = _resolve_source_ids_from_query_mentions(
                query=request.question,
                source_catalog=conversation_source_catalog,
            )
            if filename_mention_source_ids:
                # Explicit file mention should override "last active" source context.
                doc_ids_to_use = filename_mention_source_ids
                session.context_documents = [str(source_id) for source_id in filename_mention_source_ids]
                db.flush()

        explicit_source_ids = None
        fallback_source_ids = []
        if chat_history_service.enabled and doc_ids_to_use:
            fallback_source_ids = chat_history_service.upsert_sources_from_document_ids(
                db=db,
                user_id=str(current_user.id),
                document_ids=[str(doc_id) for doc_id in doc_ids_to_use],
            )
        if request.document_ids is not None:
            # Explicit source selection also includes [] to clear active sources.
            explicit_source_ids = fallback_source_ids
        elif filename_mention_source_ids:
            explicit_source_ids = fallback_source_ids or filename_mention_source_ids

        if chat_history_service.enabled:
            chat_history_service.ensure_conversation(
                conversation_id=str(session_id),
                user_id=str(current_user.id),
                title=session.title,
                session_type=session.session_type,
            )

            pre_context = chat_history_service.build_context_bundle(
                conversation_id=str(session_id),
                user_id=str(current_user.id),
                explicit_source_ids=explicit_source_ids,
            )

            resolved_source_ids = pre_context.get("source_ids") or []
            if not resolved_source_ids and fallback_source_ids:
                resolved_source_ids = fallback_source_ids

            chat_history_service.append_message(
                conversation_id=str(session_id),
                user_id=str(current_user.id),
                role="user",
                content_text=request.question,
                message_id=str(user_message.id),
                source_ids=resolved_source_ids,
                ref_type=(
                    "explicit_attachment"
                    if request.document_ids is not None
                    else ("explicit_filename_mention" if filename_mention_source_ids else "inferred_active")
                ),
                trace_id=trace_id,
            )

            context_bundle = chat_history_service.build_context_bundle(
                conversation_id=str(session_id),
                user_id=str(current_user.id),
                explicit_source_ids=explicit_source_ids,
            )

            chat_history_for_ai = context_bundle.get("chat_history") or []
            conversation_summary = context_bundle.get("conversation_summary")
            source_ids_for_ai = context_bundle.get("source_ids") or []
            source_metadata_for_ai = context_bundle.get("source_metadata") or []
        else:
            # Fallback: use relational storage if Mongo mode is disabled.
            recent_messages = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.created_at.desc()).limit(12).all()
            chat_history_for_ai = [
                {"role": m.role, "content": m.content}
                for m in reversed(recent_messages)
            ]
            conversation_summary = None
            source_ids_for_ai = []
            source_metadata_for_ai = []

        if (
            request.document_ids is None
            and len(source_ids_for_ai) > 1
            and _is_ambiguous_reference_query(request.question)
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "source_ambiguous_needs_clarification",
                    "message": "Câu hỏi đang mơ hồ giữa nhiều nguồn tri thức. Vui lòng chọn lại tài liệu cụ thể.",
                    "candidate_source_ids": source_ids_for_ai[:3],
                    "candidate_sources": source_metadata_for_ai[:3],
                    "trace_id": trace_id,
                },
            )

        ai_request = {
            "query": request.question,
            "user_id": str(current_user.id),
            "session_id": str(session_id),
            "document_ids": doc_ids_to_use,
            "top_k": request.top_k,
            "score_threshold": request.score_threshold,
            "chat_history": chat_history_for_ai,
            "conversation_summary": conversation_summary,
            "source_ids": source_ids_for_ai,
            "source_metadata": source_metadata_for_ai,
            "trace_id": trace_id,
            "persisted_by_backend": True,
        }
        
        # Add optional parameters
        if request.temperature is not None:
            ai_request["temperature"] = request.temperature
        if request.max_tokens is not None:
            ai_request["max_tokens"] = request.max_tokens

        ai_request = _json_safe(ai_request)
        
        # Call AI Service with timeout
        async with httpx.AsyncClient(timeout=300.0) as client:
            ai_response = await client.post(
                ai_service_url,
                json=ai_request
            )
            ai_response.raise_for_status()
            ai_data = ai_response.json()
        
        # 4. Save AI response message (Multi-Agent response format)
        # Extract context information from metadata if available
        metadata = ai_data.get("metadata", {})
        retrieved_contexts = metadata.get("contexts", [])
        
        ai_message = ChatMessage(
            session_id=session_id,
            user_id=current_user.id,
            role="assistant",
            content=ai_data["answer"],
            retrieved_chunks=[
                ctx.get("chunk_id") for ctx in retrieved_contexts if ctx.get("chunk_id")
            ],
            total_tokens=metadata.get("tokens_used", 0),
            confidence_score=None
        )
        db.add(ai_message)
        db.flush()

        if chat_history_service.enabled:
            token_in = int(metadata.get("token_in", 0) or 0)
            token_out = int(metadata.get("token_out", 0) or 0)
            token_total = int(metadata.get("tokens_used", token_in + token_out) or 0)
            latency_ms = int((time.time() - start_time) * 1000)

            resolved_source_ids = metadata.get("resolved_source_ids") or source_ids_for_ai
            chat_history_service.append_message(
                conversation_id=str(session_id),
                user_id=str(current_user.id),
                role="assistant",
                content_text=ai_data.get("answer", ""),
                message_id=str(ai_message.id),
                source_ids=[str(source_id) for source_id in (resolved_source_ids or [])],
                ref_type="inferred_active",
                trace_id=trace_id,
                retrieved_chunk_ids=[
                    str(chunk_id)
                    for chunk_id in [ctx.get("chunk_id") for ctx in retrieved_contexts]
                    if chunk_id
                ],
                llm_usage={
                    "token_in": token_in,
                    "token_out": token_out,
                    "token_total": token_total,
                    "latency_ms": latency_ms,
                },
                model_info={
                    "provider": metadata.get("provider") or metadata.get("model_provider"),
                    "model_name": metadata.get("model", session.model_name),
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                },
            )

            retrieval_source_ids = [
                str(document_id)
                for document_id in [ctx.get("document_id") for ctx in retrieved_contexts]
                if document_id
            ]
            if retrieval_source_ids:
                chat_history_service.add_message_source_refs(
                    message_id=str(ai_message.id),
                    conversation_id=str(session_id),
                    source_ids=retrieval_source_ids,
                    ref_type="retrieval_chunk",
                    trace_id=trace_id,
                    chunk_ids=[
                        str(chunk_id)
                        for chunk_id in [ctx.get("chunk_id") for ctx in retrieved_contexts]
                        if chunk_id
                    ],
                    confidence=0.8,
                )
        
        # 5. Update session stats
        session.message_count += 2  # User + AI messages
        session.total_tokens_used += metadata.get("tokens_used", 0)
        
        # 6. Track usage
        usage_record = AIUsageHistory(
            user_id=current_user.id,
            session_id=session_id,
            model_name=metadata.get("model", session.model_name),
            tokens_used=metadata.get("tokens_used", 0),
            request_type="chat_message",
            status="success"
        )
        db.add(usage_record)
        
        # Commit all changes
        db.commit()
        db.refresh(user_message)
        db.refresh(ai_message)

        if chat_history_service.enabled:
            chat_history_service.upsert_summary_if_needed(
                conversation_id=str(session_id),
                user_id=str(current_user.id),
                recent_window_messages=12,
            )
        
        # 7. Build response
        processing_time = time.time() - start_time
        
        # Convert contexts to response format (from metadata)
        contexts = [
            ContextChunkResponse(
                chunk_id=ctx.get("chunk_id", ""),
                document_id=ctx.get("document_id", ""),
                chunk_text=ctx.get("chunk_text", ""),
                chunk_index=ctx.get("chunk_index", 0),
                score=ctx.get("score", 0.0),
                file_name=ctx.get("file_name", ""),
                title=ctx.get("title")
            )
            for ctx in retrieved_contexts
        ]
        
        return ChatAskResponse(
            session_id=session_id,
            user_message=user_message,
            ai_message=ai_message,
            contexts=contexts,
            processing_time=processing_time,
            model_used=metadata.get("model", session.model_name),
            doc_map=metadata.get("doc_map", []),
            quota_info=metadata.get("quota_info")
        )
    
    except httpx.HTTPError as e:
        # AI Service call failed
        db.rollback()
        
        # Log error to usage history
        error_record = AIUsageHistory(
            user_id=current_user.id,
            session_id=session_id,
            model_name=session.model_name,
            tokens_used=0,
            request_type="chat_message",
            status="failed",
            error_message=str(e)
        )
        db.add(error_record)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI Service unavailable: {str(e)}"
        )

    except HTTPException:
        db.rollback()
        raise
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat request: {str(e)}"
        )
