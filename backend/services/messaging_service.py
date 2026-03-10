"""
Messaging Service - Business Logic Layer
Xử lý tin nhắn trực tiếp, nhóm, kết bạn, tìm kiếm người dùng
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, case
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone
from io import BytesIO
from PIL import Image

from models.conversations import Conversation, DirectMessage, Friendship, MessageReaction
from models.groups import Group, GroupMember, GroupMessage
from models.users import User
from services.minio_service import minio_service
from core.config import settings


class MessagingService:
    # ============================
    # Conversations
    # ============================

    @staticmethod
    def get_or_create_conversation(user_id: str, other_user_id: str, db: Session) -> Conversation:
        """Lấy hoặc tạo conversation giữa 2 người"""
        convo = db.query(Conversation).filter(
            or_(
                and_(Conversation.participant_1 == user_id, Conversation.participant_2 == other_user_id),
                and_(Conversation.participant_1 == other_user_id, Conversation.participant_2 == user_id),
            )
        ).first()

        if not convo:
            convo = Conversation(
                participant_1=user_id,
                participant_2=other_user_id,
                last_message_at=datetime.now(timezone.utc),
            )
            db.add(convo)
            db.commit()
            db.refresh(convo)

        return convo

    @staticmethod
    def get_user_conversations(user_id: str, db: Session) -> list:
        """Lấy danh sách conversations của user, sắp xếp theo thời gian mới nhất"""
        conversations = db.query(Conversation).filter(
            or_(
                Conversation.participant_1 == user_id,
                Conversation.participant_2 == user_id,
            )
        ).order_by(Conversation.last_message_at.desc()).all()

        results = []
        for convo in conversations:
            other_user_id = str(convo.participant_2) if str(convo.participant_1) == user_id else str(convo.participant_1)
            other_user = db.query(User).filter(User.id == other_user_id).first()
            unread_count = db.query(func.count(DirectMessage.id)).filter(
                DirectMessage.conversation_id == convo.id,
                DirectMessage.receiver_id == user_id,
                DirectMessage.is_read == False,
            ).scalar() or 0

            results.append({
                "conversation": convo,
                "other_user": other_user,
                "unread_count": unread_count,
            })

        return results

    @staticmethod
    def get_conversation_messages(
        conversation_id: str, user_id: str, db: Session, skip: int = 0, limit: int = 50
    ) -> List[DirectMessage]:
        """Lấy tin nhắn của conversation"""
        convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not convo:
            return []

        if str(convo.participant_1) != user_id and str(convo.participant_2) != user_id:
            return []

        messages = (
            db.query(DirectMessage)
            .filter(DirectMessage.conversation_id == conversation_id)
            .order_by(DirectMessage.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return messages

    @staticmethod
    def send_direct_message(
        conversation_id: str,
        sender_id: str,
        receiver_id: str,
        content: Optional[str],
        message_type: str,
        file_url: Optional[str],
        file_name: Optional[str],
        file_size: Optional[int],
        db: Session,
        reply_to_id: Optional[str] = None,
    ) -> DirectMessage:
        """Gửi tin nhắn trực tiếp"""
        msg = DirectMessage(
            conversation_id=conversation_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
            message_type=message_type,
            file_url=file_url,
            file_name=file_name,
            file_size=file_size,
            reply_to_id=reply_to_id,
        )
        db.add(msg)

        # Update conversation
        convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if convo:
            convo.last_message_at = datetime.now(timezone.utc)
            if message_type == "text":
                convo.last_message_content = content
            elif message_type == "image":
                convo.last_message_content = "📷 Hình ảnh"
            else:
                convo.last_message_content = f"📎 {file_name or 'Tệp đính kèm'}"

        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def mark_messages_as_delivered(message_ids: list[str], db: Session) -> list[str]:
        """Đánh dấu tin nhắn đã được gửi đến thiết bị người nhận"""
        now = datetime.now(timezone.utc)
        updated = []
        for mid in message_ids:
            msg = db.query(DirectMessage).filter(
                DirectMessage.id == mid,
                DirectMessage.delivered_at == None,
            ).first()
            if msg:
                msg.delivered_at = now
                updated.append(str(msg.id))
        if updated:
            db.commit()
        return updated

    @staticmethod
    def mark_messages_as_read(conversation_id: str, user_id: str, db: Session) -> list[str]:
        """Đánh dấu tất cả tin nhắn trong conversation đã đọc, trả về list message ids đã update"""
        now = datetime.now(timezone.utc)
        msgs = db.query(DirectMessage).filter(
            DirectMessage.conversation_id == conversation_id,
            DirectMessage.receiver_id == user_id,
            DirectMessage.is_read == False,
        ).all()
        updated_ids = []
        for msg in msgs:
            msg.is_read = True
            msg.read_at = now
            if not msg.delivered_at:
                msg.delivered_at = now
            updated_ids.append(str(msg.id))
        if updated_ids:
            db.commit()
        return updated_ids

    @staticmethod
    def get_total_unread_count(user_id: str, db: Session) -> int:
        """Tổng số tin nhắn chưa đọc của user (direct + group)"""
        # Direct message unread
        dm_unread = db.query(func.count(DirectMessage.id)).filter(
            DirectMessage.receiver_id == user_id,
            DirectMessage.is_read == False,
        ).scalar() or 0

        # Group message unread
        group_unread = 0
        memberships = db.query(GroupMember).filter(GroupMember.user_id == user_id).all()
        for membership in memberships:
            query = db.query(func.count(GroupMessage.id)).filter(
                GroupMessage.group_id == membership.group_id,
                GroupMessage.user_id != user_id,
                GroupMessage.is_deleted == False,
            )
            if membership.last_read_at:
                query = query.filter(GroupMessage.created_at > membership.last_read_at)
            group_unread += query.scalar() or 0

        return dm_unread + group_unread

    @staticmethod
    def mark_group_as_read(group_id: str, user_id: str, db: Session):
        """Mark group as read by updating last_read_at for the member"""
        membership = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        ).first()
        if membership:
            membership.last_read_at = datetime.now(timezone.utc)
            db.commit()

    # ============================
    # Group Messaging
    # ============================

    @staticmethod
    def get_user_group_conversations(user_id: str, db: Session) -> list:
        """Lấy danh sách group chats mà user tham gia"""
        groups = (
            db.query(Group)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .filter(GroupMember.user_id == user_id)
            .order_by(Group.last_message_at.desc().nullslast())
            .all()
        )
        return groups

    @staticmethod
    def get_group_messages(
        group_id: str, user_id: str, db: Session, skip: int = 0, limit: int = 50
    ) -> List[GroupMessage]:
        """Lấy tin nhắn của group"""
        member = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        ).first()
        if not member:
            return []

        messages = (
            db.query(GroupMessage)
            .filter(GroupMessage.group_id == group_id)
            .order_by(GroupMessage.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return messages

    @staticmethod
    def send_group_message(
        group_id: str,
        user_id: str,
        content: Optional[str],
        message_type: str,
        file_url: Optional[str],
        file_name: Optional[str],
        file_size: Optional[int],
        db: Session,
        reply_to_id: Optional[str] = None,
    ) -> Optional[GroupMessage]:
        """Gửi tin nhắn vào group"""
        member = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        ).first()
        if not member:
            return None

        msg = GroupMessage(
            group_id=group_id,
            user_id=user_id,
            content=content,
            message_type=message_type,
            file_url=file_url,
            file_name=file_name,
            file_size=file_size,
            reply_to_id=reply_to_id,
        )
        db.add(msg)

        # Update group
        group = db.query(Group).filter(Group.id == group_id).first()
        if group:
            group.last_message_at = datetime.now(timezone.utc)
            if message_type == "text":
                group.last_message_content = content
            elif message_type == "image":
                group.last_message_content = "📷 Hình ảnh"
            else:
                group.last_message_content = f"📎 {file_name or 'Tệp'}"

        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def get_group_members(group_id: str, db: Session) -> list:
        """Lấy danh sách thành viên group"""
        members = (
            db.query(GroupMember)
            .filter(GroupMember.group_id == group_id)
            .all()
        )
        result = []
        for m in members:
            user = db.query(User).filter(User.id == m.user_id).first()
            result.append({"member": m, "user": user})
        return result

    # ============================
    # Friendship
    # ============================

    @staticmethod
    def send_friend_request(requester_id: str, addressee_id: str, db: Session) -> Friendship:
        """Gửi lời mời kết bạn"""
        existing = db.query(Friendship).filter(
            or_(
                and_(Friendship.requester_id == requester_id, Friendship.addressee_id == addressee_id),
                and_(Friendship.requester_id == addressee_id, Friendship.addressee_id == requester_id),
            )
        ).first()

        if existing:
            return existing

        friendship = Friendship(
            requester_id=requester_id,
            addressee_id=addressee_id,
            status="pending",
        )
        db.add(friendship)
        db.commit()
        db.refresh(friendship)
        return friendship

    @staticmethod
    def respond_to_friend_request(friendship_id: str, user_id: str, action: str, db: Session) -> Optional[Friendship]:
        """Chấp nhận hoặc từ chối lời mời kết bạn"""
        friendship = db.query(Friendship).filter(
            Friendship.id == friendship_id,
            Friendship.addressee_id == user_id,
            Friendship.status == "pending",
        ).first()

        if not friendship:
            return None

        friendship.status = action  # "accepted" or "declined"
        db.commit()
        db.refresh(friendship)
        return friendship

    @staticmethod
    def get_friend_requests(user_id: str, db: Session) -> List[Friendship]:
        """Lấy danh sách lời mời kết bạn nhận được"""
        return db.query(Friendship).filter(
            Friendship.addressee_id == user_id,
            Friendship.status == "pending",
        ).all()

    @staticmethod
    def get_friends(user_id: str, db: Session) -> List[User]:
        """Lấy danh sách bạn bè"""
        friendships = db.query(Friendship).filter(
            Friendship.status == "accepted",
            or_(
                Friendship.requester_id == user_id,
                Friendship.addressee_id == user_id,
            )
        ).all()

        friend_ids = []
        for f in friendships:
            if str(f.requester_id) == user_id:
                friend_ids.append(str(f.addressee_id))
            else:
                friend_ids.append(str(f.requester_id))

        if not friend_ids:
            return []

        return db.query(User).filter(User.id.in_(friend_ids)).all()

    @staticmethod
    def search_users(query: str, current_user_id: str, db: Session) -> list:
        """Tìm kiếm người dùng theo tên hoặc mã sinh viên"""
        users = db.query(User).filter(
            User.id != current_user_id,
            User.is_active == True,
            or_(
                User.full_name.ilike(f"%{query}%"),
                User.username.ilike(f"%{query}%"),
                User.student_id == query,
            )
        ).limit(20).all()

        results = []
        for user in users:
            friendship = db.query(Friendship).filter(
                or_(
                    and_(Friendship.requester_id == current_user_id, Friendship.addressee_id == str(user.id)),
                    and_(Friendship.requester_id == str(user.id), Friendship.addressee_id == current_user_id),
                )
            ).first()

            friendship_status = None
            if friendship:
                friendship_status = friendship.status

            results.append({
                "user": user,
                "friendship_status": friendship_status,
            })

        return results

    # ============================
    # Image Compression
    # ============================

    @staticmethod
    def compress_image(file_data: bytes, max_width: int = 1920, quality: int = 80) -> tuple[bytes, str]:
        """Nén ảnh xuống HD (1920px max width), trả về (bytes, content_type)"""
        img = Image.open(BytesIO(file_data))

        # Convert RGBA to RGB if needed
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize if larger than max_width
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)

        output = BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        return output.getvalue(), "image/jpeg"

    @staticmethod
    def upload_message_file(
        file_data: bytes,
        file_name: str,
        content_type: str,
        user_id: str,
        is_image: bool = False,
    ) -> dict:
        """Upload file/ảnh cho tin nhắn lên MinIO"""
        import uuid as uuid_mod
        import os

        if is_image:
            file_data, content_type = MessagingService.compress_image(file_data)
            ext = ".jpg"
        else:
            ext = os.path.splitext(file_name)[1] if "." in file_name else ""

        unique_name = f"{uuid_mod.uuid4()}{ext}"
        object_name = f"messages/{user_id}/{unique_name}"

        file_url = minio_service.upload_file_bytes(
            file_content=file_data,
            object_name=object_name,
            content_type=content_type,
        )

        return {
            "file_url": file_url,
            "file_name": file_name,
            "file_size": len(file_data),
        }

    # ============================
    # Unified Conversation List
    # ============================

    @staticmethod
    def get_unified_conversations(user_id: str, db: Session) -> list:
        """Lấy tất cả conversations (direct + group) sắp xếp theo thời gian"""
        result = []

        # Direct conversations
        direct_convos = MessagingService.get_user_conversations(user_id, db)
        for item in direct_convos:
            convo = item["conversation"]
            other = item["other_user"]
            result.append({
                "id": str(convo.id),
                "type": "direct",
                "name": other.full_name or other.username if other else "Unknown",
                "avatar_url": other.avatar_url if other else None,
                "last_message": convo.last_message_content,
                "last_message_at": convo.last_message_at.isoformat() if convo.last_message_at else None,
                "unread_count": item["unread_count"],
                "other_user_id": str(other.id) if other else None,
                "member_count": None,
            })

        # Group conversations
        groups = MessagingService.get_user_group_conversations(user_id, db)
        for group in groups:
            # Get member avatars for group icon (last 2 members)
            members = (
                db.query(User)
                .join(GroupMember, GroupMember.user_id == User.id)
                .filter(GroupMember.group_id == group.id)
                .order_by(GroupMember.joined_at.desc())
                .limit(2)
                .all()
            )
            member_avatars = [
                {"avatar_url": m.avatar_url, "full_name": m.full_name or m.username}
                for m in members
            ]

            # Calculate group unread count using last_read_at
            membership = db.query(GroupMember).filter(
                GroupMember.group_id == group.id,
                GroupMember.user_id == user_id,
            ).first()
            group_unread = 0
            if membership:
                query = db.query(func.count(GroupMessage.id)).filter(
                    GroupMessage.group_id == group.id,
                    GroupMessage.user_id != user_id,
                    GroupMessage.is_deleted == False,
                )
                if membership.last_read_at:
                    query = query.filter(GroupMessage.created_at > membership.last_read_at)
                else:
                    # Never read — count all messages from others
                    group_unread = query.scalar() or 0
                if membership.last_read_at:
                    group_unread = query.scalar() or 0

            result.append({
                "id": str(group.id),
                "type": "group",
                "name": group.group_name,
                "avatar_url": None,
                "last_message": group.last_message_content,
                "last_message_at": group.last_message_at.isoformat() if group.last_message_at else None,
                "unread_count": group_unread,
                "other_user_id": None,
                "member_count": group.member_count,
                "member_avatars": member_avatars,
            })

        # Sort by last_message_at desc
        result.sort(key=lambda x: x["last_message_at"] or "", reverse=True)
        return result

    # ============================
    # Reactions
    # ============================

    @staticmethod
    def toggle_reaction(
        user_id: str,
        reaction: str,
        direct_message_id: Optional[str] = None,
        group_message_id: Optional[str] = None,
        db: Session = None,
    ) -> dict:
        """Toggle reaction on a message. Returns action ('added' or 'removed') and current reactions."""
        filters = [MessageReaction.user_id == user_id]
        if direct_message_id:
            filters.append(MessageReaction.direct_message_id == direct_message_id)
        else:
            filters.append(MessageReaction.group_message_id == group_message_id)

        existing = db.query(MessageReaction).filter(*filters).first()

        if existing:
            if existing.reaction == reaction:
                # Same reaction → remove it
                db.delete(existing)
                db.commit()
                action = "removed"
            else:
                # Different reaction → update
                existing.reaction = reaction
                db.commit()
                action = "added"
        else:
            new_reaction = MessageReaction(
                user_id=user_id,
                reaction=reaction,
                direct_message_id=direct_message_id,
                group_message_id=group_message_id,
            )
            db.add(new_reaction)
            db.commit()
            action = "added"

        # Return all reactions for this message
        reactions = MessagingService.get_message_reactions(
            direct_message_id=direct_message_id,
            group_message_id=group_message_id,
            db=db,
        )
        return {"action": action, "reactions": reactions}

    @staticmethod
    def get_message_reactions(
        direct_message_id: Optional[str] = None,
        group_message_id: Optional[str] = None,
        db: Session = None,
    ) -> list[dict]:
        """Get all reactions for a message, grouped by emoji with user info."""
        if direct_message_id:
            query = db.query(MessageReaction).filter(MessageReaction.direct_message_id == direct_message_id)
        else:
            query = db.query(MessageReaction).filter(MessageReaction.group_message_id == group_message_id)

        reactions = query.all()
        result = []
        for r in reactions:
            user = db.query(User).filter(User.id == r.user_id).first()
            result.append({
                "id": str(r.id),
                "user_id": str(r.user_id),
                "username": user.full_name or user.username if user else "Unknown",
                "reaction": r.reaction,
            })
        return result

    # ============================
    # Delete Message
    # ============================

    @staticmethod
    def delete_direct_message(message_id: str, user_id: str, db: Session) -> Optional[DirectMessage]:
        """Soft-delete a direct message (only sender can delete)."""
        msg = db.query(DirectMessage).filter(DirectMessage.id == message_id).first()
        if not msg:
            return None
        msg.is_deleted = True
        msg.content = None
        msg.file_url = None
        msg.file_name = None
        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def delete_group_message(message_id: str, user_id: str, db: Session) -> Optional[GroupMessage]:
        """Soft-delete a group message."""
        msg = db.query(GroupMessage).filter(GroupMessage.id == message_id).first()
        if not msg:
            return None
        msg.is_deleted = True
        msg.content = None
        msg.file_url = None
        msg.file_name = None
        db.commit()
        db.refresh(msg)
        return msg


messaging_service = MessagingService()
