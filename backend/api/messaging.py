"""
Messaging API - REST + WebSocket
Tin nhắn trực tiếp, nhóm, kết bạn, tìm kiếm người dùng
"""
import json
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

from core.databases import get_db, SessionLocal
from api.dependencies import get_current_user, CurrentUser
from services.messaging_service import messaging_service
from services.user_presence import user_presence
from services.auth_service import auth_service
from schemas.conversation import (
    ConversationCreateRequest, DirectMessageResponse, ConversationResponse,
    FriendRequestCreate, FriendRequestAction, FriendSearchResult,
    MessageSenderResponse, GroupMessageResponse, GroupMessageSenderResponse,
    UnifiedConversationResponse,
)
from models.users import User
from models.groups import Group, GroupMember, GroupMessage
from models.conversations import Conversation, DirectMessage

router = APIRouter(prefix="/api/messages", tags=["messages"])


def _get_conversation_partner_ids(user_id: str, db: Session) -> list[str]:
    """Get all user IDs that have a direct conversation with this user"""
    convos = db.query(Conversation).filter(
        (Conversation.participant_1 == user_id) | (Conversation.participant_2 == user_id)
    ).all()
    partner_ids = []
    for c in convos:
        other = str(c.participant_2) if str(c.participant_1) == user_id else str(c.participant_1)
        partner_ids.append(other)
    return partner_ids


# ============================
# WebSocket Connection Manager
# ============================
class ConnectionManager:
    def __init__(self):
        # user_id -> list of WebSocket connections
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        await user_presence.mark_user_online(user_id)

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id] = [
                ws for ws in self.active_connections[user_id] if ws != websocket
            ]
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_to_user(self, user_id: str, message: dict):
        if user_id in self.active_connections:
            data = json.dumps(message, default=str)
            for ws in self.active_connections[user_id]:
                try:
                    await ws.send_text(data)
                except Exception:
                    pass

    async def send_to_group(self, group_member_ids: list[str], message: dict, exclude_user: str = None):
        for uid in group_member_ids:
            if uid != exclude_user:
                await self.send_to_user(uid, message)


manager = ConnectionManager()


# ============================
# WebSocket Endpoint
# ============================
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    """WebSocket endpoint cho real-time messaging"""
    if not token:
        await websocket.close(code=4001)
        return

    db = SessionLocal()
    try:
        user = await auth_service.get_current_user_from_token(token, db)
    except Exception:
        await websocket.close(code=4001)
        db.close()
        return

    user_id = str(user.id)
    await manager.connect(websocket, user_id)
    await user_presence.mark_user_online(user_id)

    # Broadcast online status to conversation partners
    partner_ids = _get_conversation_partner_ids(user_id, db)
    for pid in partner_ids:
        await manager.send_to_user(pid, {
            "type": "presence_update",
            "user_id": user_id,
            "is_online": True,
            "last_activity": None,
        })

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type")

            if msg_type == "ping":
                await user_presence.update_user_activity(user_id)
                await websocket.send_text(json.dumps({"type": "pong"}))

            elif msg_type == "direct_message":
                conversation_id = msg.get("conversation_id")
                receiver_id = msg.get("receiver_id")
                content = msg.get("content")
                message_type = msg.get("message_type", "text")
                file_url = msg.get("file_url")
                file_name = msg.get("file_name")
                file_size = msg.get("file_size")
                reply_to_id = msg.get("reply_to_id")

                if not conversation_id or not receiver_id:
                    continue

                dm = messaging_service.send_direct_message(
                    conversation_id=conversation_id,
                    sender_id=user_id,
                    receiver_id=receiver_id,
                    content=content,
                    message_type=message_type,
                    file_url=file_url,
                    file_name=file_name,
                    file_size=file_size,
                    db=db,
                    reply_to_id=reply_to_id,
                )

                # Build reply_to info if present
                reply_to_data = None
                if dm.reply_to_id:
                    from models.conversations import DirectMessage as DM_model
                    replied = db.query(DM_model).filter(DM_model.id == dm.reply_to_id).first()
                    if replied:
                        replied_sender = db.query(User).filter(User.id == replied.sender_id).first()
                        reply_to_data = {
                            "id": str(replied.id),
                            "content": replied.content if not replied.is_deleted else None,
                            "sender_name": replied_sender.full_name or replied_sender.username if replied_sender else "Unknown",
                            "message_type": replied.message_type,
                            "is_deleted": replied.is_deleted,
                            "file_url": replied.file_url if not replied.is_deleted else None,
                        }

                response = {
                    "type": "new_direct_message",
                    "message": {
                        "id": str(dm.id),
                        "conversation_id": str(dm.conversation_id),
                        "sender_id": str(dm.sender_id),
                        "receiver_id": str(dm.receiver_id),
                        "content": dm.content,
                        "message_type": dm.message_type,
                        "file_url": dm.file_url,
                        "file_name": dm.file_name,
                        "file_size": dm.file_size,
                        "is_read": dm.is_read,
                        "status": dm.status,
                        "delivered_at": dm.delivered_at.isoformat() if dm.delivered_at else None,
                        "read_at": dm.read_at.isoformat() if dm.read_at else None,
                        "created_at": dm.created_at.isoformat(),
                        "reply_to_id": str(dm.reply_to_id) if dm.reply_to_id else None,
                        "reply_to": reply_to_data,
                        "is_deleted": dm.is_deleted,
                        "reactions": [],
                        "sender": {
                            "id": str(user.id),
                            "username": user.username,
                            "full_name": user.full_name,
                            "avatar_url": user.avatar_url,
                        },
                    },
                }

                # Send to sender
                await manager.send_to_user(user_id, response)
                # Send to receiver
                await manager.send_to_user(receiver_id, response)

            elif msg_type == "group_message":
                group_id = msg.get("group_id")
                content = msg.get("content")
                message_type = msg.get("message_type", "text")
                file_url = msg.get("file_url")
                file_name = msg.get("file_name")
                file_size = msg.get("file_size")
                reply_to_id = msg.get("reply_to_id")

                if not group_id:
                    continue

                gm = messaging_service.send_group_message(
                    group_id=group_id,
                    user_id=user_id,
                    content=content,
                    message_type=message_type,
                    file_url=file_url,
                    file_name=file_name,
                    file_size=file_size,
                    db=db,
                    reply_to_id=reply_to_id,
                )

                if gm:
                    members = messaging_service.get_group_members(group_id, db)
                    member_ids = [str(m["user"].id) for m in members if m["user"]]

                    reply_to_data = None
                    if gm.reply_to_id:
                        replied = db.query(GroupMessage).filter(GroupMessage.id == gm.reply_to_id).first()
                        if replied:
                            replied_sender = db.query(User).filter(User.id == replied.user_id).first()
                            reply_to_data = {
                                "id": str(replied.id),
                                "content": replied.content if not replied.is_deleted else None,
                                "sender_name": replied_sender.full_name or replied_sender.username if replied_sender else "Unknown",
                                "message_type": replied.message_type,
                                "is_deleted": replied.is_deleted,
                                "file_url": replied.file_url if not replied.is_deleted else None,
                            }

                    response = {
                        "type": "new_group_message",
                        "message": {
                            "id": str(gm.id),
                            "group_id": str(gm.group_id),
                            "user_id": str(gm.user_id),
                            "content": gm.content,
                            "message_type": gm.message_type,
                            "file_url": gm.file_url,
                            "file_name": gm.file_name,
                            "file_size": gm.file_size,
                            "is_pinned": gm.is_pinned,
                            "created_at": gm.created_at.isoformat(),
                            "reply_to_id": str(gm.reply_to_id) if gm.reply_to_id else None,
                            "reply_to": reply_to_data,
                            "is_deleted": gm.is_deleted,
                            "reactions": [],
                            "sender": {
                                "id": str(user.id),
                                "username": user.username,
                                "full_name": user.full_name,
                                "avatar_url": user.avatar_url,
                            },
                        },
                    }
                    await manager.send_to_group(member_ids, response)

            elif msg_type == "msg_delivered":
                # Receiver acknowledges receipt of messages
                message_ids = msg.get("message_ids", [])
                if message_ids:
                    updated = messaging_service.mark_messages_as_delivered(message_ids, db)
                    if updated:
                        # Find sender(s) and notify them
                        from models.conversations import DirectMessage as DM
                        for mid in updated:
                            dm = db.query(DM).filter(DM.id == mid).first()
                            if dm:
                                await manager.send_to_user(str(dm.sender_id), {
                                    "type": "msg_status_update",
                                    "message_ids": [mid],
                                    "status": "delivered",
                                    "conversation_id": str(dm.conversation_id),
                                    "delivered_at": dm.delivered_at.isoformat() if dm.delivered_at else None,
                                })

            elif msg_type == "msg_read":
                # Receiver has opened/focused the conversation
                conversation_id = msg.get("conversation_id")
                if conversation_id:
                    updated_ids = messaging_service.mark_messages_as_read(conversation_id, user_id, db)
                    if updated_ids:
                        # Find the other participant and notify
                        from models.conversations import Conversation as Conv
                        convo = db.query(Conv).filter(Conv.id == conversation_id).first()
                        if convo:
                            other_id = str(convo.participant_2) if str(convo.participant_1) == user_id else str(convo.participant_1)
                            now_iso = datetime.now(timezone.utc).isoformat()
                            await manager.send_to_user(other_id, {
                                "type": "msg_status_update",
                                "message_ids": updated_ids,
                                "status": "seen",
                                "conversation_id": conversation_id,
                                "read_at": now_iso,
                            })
                            # Also send unread_count update to reader
                            total_unread = messaging_service.get_total_unread_count(user_id, db)
                            await manager.send_to_user(user_id, {
                                "type": "unread_count_update",
                                "total_unread": total_unread,
                            })

            elif msg_type == "mark_read":
                # Legacy compatibility
                conversation_id = msg.get("conversation_id")
                if conversation_id:
                    messaging_service.mark_messages_as_read(conversation_id, user_id, db)

            elif msg_type == "group_msg_read":
                # User has opened/focused a group conversation
                group_id = msg.get("group_id")
                if group_id:
                    messaging_service.mark_group_as_read(group_id, user_id, db)
                    total_unread = messaging_service.get_total_unread_count(user_id, db)
                    await manager.send_to_user(user_id, {
                        "type": "unread_count_update",
                        "total_unread": total_unread,
                    })

            elif msg_type == "typing":
                # Forward typing indicator
                target_id = msg.get("target_id")
                target_type = msg.get("target_type", "direct")
                if target_type == "direct" and target_id:
                    await manager.send_to_user(target_id, {
                        "type": "typing",
                        "user_id": user_id,
                        "username": user.full_name or user.username,
                        "conversation_id": msg.get("conversation_id"),
                    })

            elif msg_type == "react_message":
                # Toggle reaction on a message
                message_id = msg.get("message_id")
                reaction = msg.get("reaction")
                msg_scope = msg.get("scope", "direct")  # "direct" or "group"
                if not message_id or not reaction:
                    continue

                try:
                    dm_id = message_id if msg_scope == "direct" else None
                    gm_id = message_id if msg_scope == "group" else None

                    result = messaging_service.toggle_reaction(
                        user_id=user_id,
                        reaction=reaction,
                        direct_message_id=dm_id,
                        group_message_id=gm_id,
                        db=db,
                    )

                    event = {
                        "type": "reaction_update",
                        "message_id": message_id,
                        "scope": msg_scope,
                        "reactions": result["reactions"],
                        "conversation_id": msg.get("conversation_id"),
                        "group_id": msg.get("group_id"),
                    }

                    if msg_scope == "direct":
                        convo_id = msg.get("conversation_id")
                        if convo_id:
                            from models.conversations import Conversation as Conv
                            convo = db.query(Conv).filter(Conv.id == convo_id).first()
                            if convo:
                                await manager.send_to_user(str(convo.participant_1), event)
                                await manager.send_to_user(str(convo.participant_2), event)
                    else:
                        g_id = msg.get("group_id")
                        if g_id:
                            members = messaging_service.get_group_members(g_id, db)
                            member_ids = [str(m["user"].id) for m in members if m["user"]]
                            await manager.send_to_group(member_ids, event)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    db.rollback()

            elif msg_type == "delete_message":
                message_id = msg.get("message_id")
                msg_scope = msg.get("scope", "direct")
                if not message_id:
                    continue

                if msg_scope == "direct":
                    deleted = messaging_service.delete_direct_message(message_id, user_id, db)
                    if deleted:
                        event = {
                            "type": "message_deleted",
                            "message_id": message_id,
                            "scope": "direct",
                            "conversation_id": str(deleted.conversation_id),
                        }
                        await manager.send_to_user(str(deleted.sender_id), event)
                        await manager.send_to_user(str(deleted.receiver_id), event)
                else:
                    deleted = messaging_service.delete_group_message(message_id, user_id, db)
                    if deleted:
                        members = messaging_service.get_group_members(str(deleted.group_id), db)
                        member_ids = [str(m["user"].id) for m in members if m["user"]]
                        event = {
                            "type": "message_deleted",
                            "message_id": message_id,
                            "scope": "group",
                            "group_id": str(deleted.group_id),
                        }
                        await manager.send_to_group(member_ids, event)

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        await user_presence.mark_user_offline(user_id)
        # Broadcast offline to conversation partners
        for pid in partner_ids:
            await manager.send_to_user(pid, {
                "type": "presence_update",
                "user_id": user_id,
                "is_online": False,
                "last_activity": "Vừa mới",
            })
    except Exception:
        manager.disconnect(websocket, user_id)
        await user_presence.mark_user_offline(user_id)
        for pid in partner_ids:
            await manager.send_to_user(pid, {
                "type": "presence_update",
                "user_id": user_id,
                "is_online": False,
                "last_activity": "Vừa mới",
            })
    finally:
        db.close()


# ============================
# REST Endpoints
# ============================

@router.get("/conversations")
async def get_conversations(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Lấy tất cả conversations (direct + group) thống nhất"""
    conversations = messaging_service.get_unified_conversations(str(current_user.id), db)

    # Enrich with online status
    for convo in conversations:
        if convo["type"] == "direct" and convo["other_user_id"]:
            is_online = await user_presence.is_user_online(convo["other_user_id"])
            convo["is_online"] = is_online
            if not is_online:
                last_active = await user_presence.get_user_last_activity(convo["other_user_id"])
                if last_active:
                    from datetime import datetime, timezone
                    now = datetime.now(timezone.utc)
                    diff = now - last_active.replace(tzinfo=timezone.utc) if last_active.tzinfo is None else now - last_active
                    minutes = int(diff.total_seconds() / 60)
                    if minutes < 1:
                        convo["last_activity"] = "Vừa mới"
                    elif minutes < 60:
                        convo["last_activity"] = f"{minutes} phút trước"
                    elif minutes < 300:
                        convo["last_activity"] = f"{minutes // 60} giờ trước"
                    else:
                        convo["last_activity"] = "Offline"
                else:
                    convo["last_activity"] = "Offline"
            else:
                convo["last_activity"] = None

    return conversations


@router.post("/conversations")
async def create_conversation(
    request: ConversationCreateRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Tạo hoặc lấy conversation với người dùng khác"""
    other_user = db.query(User).filter(User.id == request.participant_2_id).first()
    if not other_user:
        raise HTTPException(status_code=404, detail="User not found")

    convo = messaging_service.get_or_create_conversation(
        str(current_user.id), str(other_user.id), db
    )

    return {
        "id": str(convo.id),
        "participant_1": str(convo.participant_1),
        "participant_2": str(convo.participant_2),
        "last_message_at": convo.last_message_at.isoformat() if convo.last_message_at else None,
        "other_user": {
            "id": str(other_user.id),
            "username": other_user.username,
            "full_name": other_user.full_name,
            "avatar_url": other_user.avatar_url,
            "student_id": other_user.student_id,
        },
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Lấy tin nhắn của conversation"""
    messages = messaging_service.get_conversation_messages(
        conversation_id, str(current_user.id), db, skip, limit
    )

    result = []
    for msg in messages:
        sender = db.query(User).filter(User.id == msg.sender_id).first()

        # Build reply_to info
        reply_to_data = None
        if msg.reply_to_id:
            replied = db.query(DirectMessage).filter(DirectMessage.id == msg.reply_to_id).first()
            if replied:
                replied_sender = db.query(User).filter(User.id == replied.sender_id).first()
                reply_to_data = {
                    "id": str(replied.id),
                    "content": replied.content if not replied.is_deleted else None,
                    "sender_name": replied_sender.full_name or replied_sender.username if replied_sender else "Unknown",
                    "message_type": replied.message_type,
                    "is_deleted": replied.is_deleted,
                    "file_url": replied.file_url if not replied.is_deleted else None,
                }

        # Build reactions
        reactions = messaging_service.get_message_reactions(direct_message_id=str(msg.id), db=db)

        result.append({
            "id": str(msg.id),
            "conversation_id": str(msg.conversation_id),
            "sender_id": str(msg.sender_id),
            "receiver_id": str(msg.receiver_id),
            "content": msg.content,
            "message_type": msg.message_type,
            "file_url": msg.file_url,
            "file_name": msg.file_name,
            "file_size": msg.file_size,
            "is_read": msg.is_read,
            "status": msg.status,
            "delivered_at": msg.delivered_at.isoformat() if msg.delivered_at else None,
            "read_at": msg.read_at.isoformat() if msg.read_at else None,
            "created_at": msg.created_at.isoformat(),
            "reply_to_id": str(msg.reply_to_id) if msg.reply_to_id else None,
            "reply_to": reply_to_data,
            "is_deleted": msg.is_deleted,
            "reactions": reactions,
            "sender": {
                "id": str(sender.id),
                "username": sender.username,
                "full_name": sender.full_name,
                "avatar_url": sender.avatar_url,
            } if sender else None,
        })

    # Mark as read
    messaging_service.mark_messages_as_read(conversation_id, str(current_user.id), db)

    return result


@router.get("/groups/{group_id}/messages")
async def get_group_messages(
    group_id: str,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Lấy tin nhắn của group"""
    messages = messaging_service.get_group_messages(
        group_id, str(current_user.id), db, skip, limit
    )

    result = []
    for msg in messages:
        sender = db.query(User).filter(User.id == msg.user_id).first()

        reply_to_data = None
        if msg.reply_to_id:
            replied = db.query(GroupMessage).filter(GroupMessage.id == msg.reply_to_id).first()
            if replied:
                replied_sender = db.query(User).filter(User.id == replied.user_id).first()
                reply_to_data = {
                    "id": str(replied.id),
                    "content": replied.content if not replied.is_deleted else None,
                    "sender_name": replied_sender.full_name or replied_sender.username if replied_sender else "Unknown",
                    "message_type": replied.message_type,
                    "is_deleted": replied.is_deleted,
                    "file_url": replied.file_url if not replied.is_deleted else None,
                }

        reactions = messaging_service.get_message_reactions(group_message_id=str(msg.id), db=db)

        result.append({
            "id": str(msg.id),
            "group_id": str(msg.group_id),
            "user_id": str(msg.user_id),
            "content": msg.content,
            "message_type": msg.message_type,
            "file_url": msg.file_url,
            "file_name": msg.file_name,
            "file_size": msg.file_size,
            "is_pinned": msg.is_pinned,
            "created_at": msg.created_at.isoformat(),
            "reply_to_id": str(msg.reply_to_id) if msg.reply_to_id else None,
            "reply_to": reply_to_data,
            "is_deleted": msg.is_deleted,
            "reactions": reactions,
            "sender": {
                "id": str(sender.id),
                "username": sender.username,
                "full_name": sender.full_name,
                "avatar_url": sender.avatar_url,
            } if sender else None,
        })

    return result


@router.get("/groups/{group_id}/members")
async def get_group_members(
    group_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Lấy danh sách thành viên group"""
    members = messaging_service.get_group_members(group_id, db)
    result = []
    for m in members:
        user = m["user"]
        if user:
            is_online = await user_presence.is_user_online(str(user.id))
            result.append({
                "id": str(user.id),
                "username": user.username,
                "full_name": user.full_name,
                "avatar_url": user.avatar_url,
                "role": m["member"].role,
                "is_online": is_online,
            })
    return result


# ============================
# File Upload
# ============================
@router.post("/upload")
async def upload_message_file(
    current_user: CurrentUser,
    file: UploadFile = File(...),
):
    """Upload file/ảnh cho tin nhắn"""
    allowed_image_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
    max_file_size = 25 * 1024 * 1024  # 25MB

    file_content = await file.read()
    if len(file_content) > max_file_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 25MB limit",
        )

    is_image = file.content_type in allowed_image_types

    result = messaging_service.upload_message_file(
        file_data=file_content,
        file_name=file.filename or "file",
        content_type=file.content_type or "application/octet-stream",
        user_id=str(current_user.id),
        is_image=is_image,
    )

    return {
        "file_url": result["file_url"],
        "file_name": result["file_name"],
        "file_size": result["file_size"],
        "message_type": "image" if is_image else "file",
    }


# ============================
# Unread Count
# ============================
@router.get("/unread-count")
async def get_unread_count(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Lấy tổng số tin nhắn chưa đọc"""
    total = messaging_service.get_total_unread_count(str(current_user.id), db)
    return {"total_unread": total}


# ============================
# Friendship
# ============================
@router.get("/users/search")
async def search_users(
    current_user: CurrentUser,
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    """Tìm kiếm người dùng theo tên hoặc mã sinh viên"""
    results = messaging_service.search_users(q, str(current_user.id), db)
    return [
        {
            "id": str(r["user"].id),
            "username": r["user"].username,
            "full_name": r["user"].full_name,
            "student_id": r["user"].student_id,
            "avatar_url": r["user"].avatar_url,
            "friendship_status": r["friendship_status"],
        }
        for r in results
    ]


@router.post("/friends/request")
async def send_friend_request(
    request: FriendRequestCreate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Gửi lời mời kết bạn"""
    if str(request.addressee_id) == str(current_user.id):
        raise HTTPException(status_code=400, detail="Cannot send friend request to yourself")

    friendship = messaging_service.send_friend_request(
        str(current_user.id), str(request.addressee_id), db
    )

    # Notify via WebSocket
    await manager.send_to_user(str(request.addressee_id), {
        "type": "friend_request",
        "from": {
            "id": str(current_user.id),
            "username": current_user.username,
            "full_name": current_user.full_name,
            "avatar_url": current_user.avatar_url,
        },
        "friendship_id": str(friendship.id),
        "status": friendship.status,
    })

    return {
        "id": str(friendship.id),
        "status": friendship.status,
    }


@router.post("/friends/{friendship_id}/respond")
async def respond_to_friend_request(
    friendship_id: str,
    request: FriendRequestAction,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Chấp nhận hoặc từ chối lời mời kết bạn"""
    if request.action not in ("accepted", "declined"):
        raise HTTPException(status_code=400, detail="Action must be 'accepted' or 'declined'")

    friendship = messaging_service.respond_to_friend_request(
        friendship_id, str(current_user.id), request.action, db
    )

    if not friendship:
        raise HTTPException(status_code=404, detail="Friend request not found")

    return {"id": str(friendship.id), "status": friendship.status}


@router.get("/friends")
async def get_friends(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Lấy danh sách bạn bè"""
    friends = messaging_service.get_friends(str(current_user.id), db)
    result = []
    for f in friends:
        is_online = await user_presence.is_user_online(str(f.id))
        result.append({
            "id": str(f.id),
            "username": f.username,
            "full_name": f.full_name,
            "student_id": f.student_id,
            "avatar_url": f.avatar_url,
            "is_online": is_online,
        })
    return result


@router.get("/friends/requests")
async def get_friend_requests(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Lấy danh sách lời mời kết bạn"""
    requests = messaging_service.get_friend_requests(str(current_user.id), db)
    result = []
    for r in requests:
        requester = db.query(User).filter(User.id == r.requester_id).first()
        if requester:
            result.append({
                "id": str(r.id),
                "requester": {
                    "id": str(requester.id),
                    "username": requester.username,
                    "full_name": requester.full_name,
                    "avatar_url": requester.avatar_url,
                    "student_id": requester.student_id,
                },
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            })
    return result


@router.get("/online-status/{user_id}")
async def get_user_online_status(
    user_id: str,
    current_user: CurrentUser,
):
    """Lấy trạng thái online của user"""
    is_online = await user_presence.is_user_online(user_id)
    last_activity = None
    if not is_online:
        last_active = await user_presence.get_user_last_activity(user_id)
        if last_active:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            diff = now - last_active.replace(tzinfo=timezone.utc) if last_active.tzinfo is None else now - last_active
            minutes = int(diff.total_seconds() / 60)
            if minutes < 1:
                last_activity = "Vừa mới"
            elif minutes < 60:
                last_activity = f"{minutes} phút trước"
            elif minutes < 300:
                last_activity = f"{minutes // 60} giờ trước"
            else:
                last_activity = "Offline"
        else:
            last_activity = "Offline"

    return {
        "user_id": user_id,
        "is_online": is_online,
        "last_activity": last_activity,
    }


# ============================================
# Media & Files for conversations
# ============================================
@router.get("/conversations/{conversation_id}/media")
async def get_conversation_media(
    conversation_id: str,
    current_user: CurrentUser,
    media_type: str = "image",
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Lấy media/files của cuộc trò chuyện trực tiếp"""
    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    uid = str(current_user.id)
    if str(convo.participant_1) != uid and str(convo.participant_2) != uid:
        raise HTTPException(status_code=403, detail="Not a participant")

    types = ["image"] if media_type == "image" else ["file"]

    messages = (
        db.query(DirectMessage)
        .filter(
            DirectMessage.conversation_id == conversation_id,
            DirectMessage.message_type.in_(types),
            DirectMessage.is_deleted == False,
        )
        .order_by(DirectMessage.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    result = []
    for msg in messages:
        sender = db.query(User).filter(User.id == msg.sender_id).first()
        result.append({
            "id": str(msg.id),
            "file_url": msg.file_url,
            "file_name": msg.file_name,
            "file_size": msg.file_size,
            "message_type": msg.message_type,
            "created_at": msg.created_at.isoformat(),
            "sender": {
                "id": str(sender.id),
                "full_name": sender.full_name,
                "username": sender.username,
            } if sender else None,
        })

    return result


@router.get("/groups/{group_id}/media")
async def get_group_media(
    group_id: str,
    current_user: CurrentUser,
    media_type: str = "image",
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Lấy media/files của nhóm"""
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == current_user.id,
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a group member")

    types = ["image"] if media_type == "image" else ["file"]

    messages = (
        db.query(GroupMessage)
        .filter(
            GroupMessage.group_id == group_id,
            GroupMessage.message_type.in_(types),
            GroupMessage.is_deleted == False,
        )
        .order_by(GroupMessage.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    result = []
    for msg in messages:
        sender = db.query(User).filter(User.id == msg.user_id).first()
        result.append({
            "id": str(msg.id),
            "file_url": msg.file_url,
            "file_name": msg.file_name,
            "file_size": msg.file_size,
            "message_type": msg.message_type,
            "created_at": msg.created_at.isoformat(),
            "sender": {
                "id": str(sender.id),
                "full_name": sender.full_name,
                "username": sender.username,
            } if sender else None,
        })

    return result
