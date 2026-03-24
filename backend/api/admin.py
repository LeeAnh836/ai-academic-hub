"""
Admin API routes - Dashboard stats, User/Group/Document/Log management
Tất cả routes yêu cầu admin role
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, case
from datetime import datetime, timezone, timedelta
from typing import Optional

from core.databases import get_db
from api.dependencies import AdminUser
from services.user_presence import user_presence
from models.users import User, LoginHistory
from models.documents import Document, DocumentShare
from models.groups import Group, GroupMember, GroupFile
from models.chat import ChatSession
from schemas.admin import (
    AdminStatsResponse,
    AdminUserResponse,
    AdminUserListResponse,
    AdminGroupResponse,
    AdminGroupListResponse,
    AdminDocumentResponse,
    AdminDocumentListResponse,
    AdminActivityLogResponse,
    AdminActivityLogListResponse,
    ChangeUserRoleRequest,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
)


# ============================================
# Helpers
# ============================================

def _format_file_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def _time_ago(dt: datetime) -> str:
    """Convert datetime to relative time string"""
    if dt is None:
        return "Never"
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())

    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        mins = seconds // 60
        return f"{mins}m ago"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours}h ago"
    elif seconds < 604800:
        days = seconds // 86400
        return f"{days}d ago"
    else:
        return dt.strftime("%Y-%m-%d")


# ============================================
# GET /api/admin/stats - Dashboard statistics
# ============================================
@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    """
    Lấy thống kê tổng quan cho admin dashboard
    """
    # Total users
    total_users = db.query(func.count(User.id)).scalar() or 0

    # Active today: users with login history today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    active_today_count = (
        db.query(func.count(distinct(LoginHistory.user_id)))
        .filter(
            LoginHistory.created_at >= today_start,
            LoginHistory.status == "success",
        )
        .scalar()
        or 0
    )

    # Also count currently online users from Redis
    try:
        online_users = await user_presence.get_online_users()
        # Active today = max of login-history count and online user count
        active_today = max(active_today_count, len(online_users))
    except Exception:
        active_today = active_today_count

    # Total groups
    total_groups = db.query(func.count(Group.id)).scalar() or 0

    # Total files (documents)
    total_files = db.query(func.count(Document.id)).scalar() or 0

    # Total AI chat sessions
    total_ai_chats = db.query(func.count(ChatSession.id)).scalar() or 0

    # Total storage used (sum of all document file sizes)
    total_storage = db.query(func.sum(Document.file_size)).scalar() or 0
    storage_used = _format_file_size(total_storage)

    return AdminStatsResponse(
        total_users=total_users,
        active_today=active_today,
        total_groups=total_groups,
        total_files=total_files,
        total_ai_chats=total_ai_chats,
        storage_used=storage_used,
    )


# ============================================
# GET /api/admin/users - List all users
# ============================================
@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    admin: AdminUser,
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Search by name, email, or student_id"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Danh sách tất cả users - có search, phân trang, trạng thái online từ Redis
    """
    query = db.query(User)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.full_name.ilike(search_term))
            | (User.email.ilike(search_term))
            | (User.username.ilike(search_term))
            | (User.student_id.ilike(search_term))
        )

    total = query.count()
    users = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # Batch get online status from Redis
    try:
        online_user_ids = set(await user_presence.get_online_users())
    except Exception:
        online_user_ids = set()

    user_list = []
    for u in users:
        uid = str(u.id)
        is_online = uid in online_user_ids

        if is_online:
            last_seen_str = "Now"
        else:
            last_activity = await user_presence.get_user_last_activity(uid)
            if last_activity:
                last_seen_str = _time_ago(last_activity)
            elif u.last_login_at:
                last_seen_str = _time_ago(u.last_login_at)
            else:
                last_seen_str = "Never"

        user_list.append(
            AdminUserResponse(
                id=u.id,
                email=u.email,
                username=u.username,
                full_name=u.full_name,
                avatar_url=u.avatar_url,
                role=u.role,
                student_id=u.student_id,
                is_active=u.is_active,
                is_verified=u.is_verified,
                online=is_online,
                last_seen=last_seen_str,
                created_at=u.created_at,
            )
        )

    return AdminUserListResponse(
        users=user_list,
        total=total,
        page=page,
        page_size=page_size,
    )


# ============================================
# PUT /api/admin/users/{user_id}/role - Change user role
# ============================================
@router.put("/users/{user_id}/role")
async def change_user_role(
    user_id: str,
    request: ChangeUserRoleRequest,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    """
    Thay đổi role của user (admin/user)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if str(user.id) == str(admin.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change your own role")

    user.role = request.role
    db.commit()
    return {"message": f"User role changed to {request.role}"}


# ============================================
# PUT /api/admin/users/{user_id}/ban - Ban (deactivate) user
# ============================================
@router.put("/users/{user_id}/ban")
async def ban_user(
    user_id: str,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    """
    Ban (deactivate) user hoặc unban nếu đã bị ban
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if str(user.id) == str(admin.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot ban yourself")

    user.is_active = not user.is_active
    db.commit()

    status_text = "unbanned" if user.is_active else "banned"
    return {"message": f"User {status_text}", "is_active": user.is_active}


# ============================================
# DELETE /api/admin/users/{user_id} - Delete user
# ============================================
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    """
    Xóa user vĩnh viễn
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if str(user.id) == str(admin.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")

    db.delete(user)
    db.commit()
    return {"message": "User deleted"}


# ============================================
# GET /api/admin/groups - List all groups
# ============================================
@router.get("/groups", response_model=AdminGroupListResponse)
async def list_groups(
    admin: AdminUser,
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Search by group name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Danh sách tất cả groups
    """
    query = db.query(Group)

    if search:
        search_term = f"%{search}%"
        query = query.filter(Group.group_name.ilike(search_term))

    total = query.count()
    groups = query.order_by(Group.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    group_list = []
    for g in groups:
        # Count files in group
        file_count = db.query(func.count(GroupFile.id)).filter(GroupFile.group_id == g.id).scalar() or 0

        last_active_str = _time_ago(g.last_message_at) if g.last_message_at else _time_ago(g.created_at)

        group_list.append(
            AdminGroupResponse(
                id=g.id,
                name=g.group_name,
                description=g.description,
                members=g.member_count,
                files=file_count,
                last_active=last_active_str,
                created_at=g.created_at,
            )
        )

    return AdminGroupListResponse(
        groups=group_list,
        total=total,
        page=page,
        page_size=page_size,
    )


# ============================================
# DELETE /api/admin/groups/{group_id} - Delete group
# ============================================
@router.delete("/groups/{group_id}")
async def delete_group(
    group_id: str,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    """
    Xóa group vĩnh viễn
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    db.delete(group)
    db.commit()
    return {"message": "Group deleted"}


# ============================================
# GET /api/admin/documents - List all documents
# ============================================
@router.get("/documents", response_model=AdminDocumentListResponse)
async def list_documents(
    admin: AdminUser,
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Search by file name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Danh sách tất cả documents/files
    """
    query = db.query(Document).join(User, Document.user_id == User.id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Document.title.ilike(search_term))
            | (Document.file_name.ilike(search_term))
        )

    total = query.count()
    docs = (
        query.order_by(Document.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    doc_list = []
    for d in docs:
        owner = db.query(User).filter(User.id == d.user_id).first()
        owner_name = (owner.full_name or owner.username) if owner else "Unknown"
        owner_id = owner.id if owner else d.user_id

        # Check if document is shared
        share_count = db.query(func.count(DocumentShare.id)).filter(DocumentShare.document_id == d.id).scalar() or 0

        doc_list.append(
            AdminDocumentResponse(
                id=d.id,
                name=d.title or d.file_name,
                file_type=d.file_type,
                size=_format_file_size(d.file_size),
                owner=owner_name,
                owner_id=owner_id,
                shared=share_count > 0,
                updated_at=d.updated_at,
                created_at=d.created_at,
            )
        )

    return AdminDocumentListResponse(
        documents=doc_list,
        total=total,
        page=page,
        page_size=page_size,
    )


# ============================================
# DELETE /api/admin/documents/{document_id} - Delete document
# ============================================
@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    """
    Xóa document vĩnh viễn
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    db.delete(doc)
    db.commit()
    return {"message": "Document deleted"}


# ============================================
# GET /api/admin/activity-logs - Login & activity logs
# ============================================
@router.get("/activity-logs", response_model=AdminActivityLogListResponse)
async def list_activity_logs(
    admin: AdminUser,
    db: Session = Depends(get_db),
    today_only: bool = Query(True, description="Only show today's logs"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """
    Lấy lịch sử đăng nhập/hoạt động từ LoginHistory
    Mặc định chỉ hiện logs trong ngày hôm nay
    """
    query = db.query(LoginHistory).join(User, LoginHistory.user_id == User.id)

    if today_only:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(LoginHistory.created_at >= today_start)

    total = query.count()
    logs = (
        query.order_by(LoginHistory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    log_list = []
    for log in logs:
        user = db.query(User).filter(User.id == log.user_id).first()
        user_name = (user.full_name or user.username) if user else "Unknown"

        if log.status == "success":
            action = "Logged in successfully"
        else:
            action = f"Login failed: {log.failed_reason or 'Unknown reason'}"

        log_list.append(
            AdminActivityLogResponse(
                id=log.id,
                user=user_name,
                action=action,
                target=None,
                ip_address=log.ip_address,
                timestamp=_time_ago(log.created_at),
                created_at=log.created_at,
            )
        )

    return AdminActivityLogListResponse(
        logs=log_list,
        total=total,
        page=page,
        page_size=page_size,
    )
