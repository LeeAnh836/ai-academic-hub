"""
Group routes - Groups management
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from core.databases import get_db
from api.dependencies import get_current_user, CurrentUser
from schemas.group import (
    GroupResponse, GroupCreateRequest, GroupUpdateRequest,
    GroupMemberAddRequest, GroupMessageCreateRequest, GroupDetailResponse,
    GroupFileShareRequest
)
from models.users import User
from models.groups import Group, GroupMember, GroupMessage, GroupFile

router = APIRouter(
    prefix="/api/groups", 
    tags=["groups"],
    dependencies=[Depends(get_current_user)]  # Apply authentication to all endpoints
)


# ============================================
# List groups
# ============================================
@router.get("")
async def list_groups(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 10
):
    """
    Lấy danh sách groups của user, kèm avatar 2 member mới nhất
    """
    # Lấy groups mà user đã join
    member_groups = db.query(Group).join(GroupMember).filter(
        GroupMember.user_id == current_user.id
    ).offset(skip).limit(limit).all()
    
    result = []
    for group in member_groups:
        # Get last 2 members for avatar display
        recent_members = db.query(GroupMember).filter(
            GroupMember.group_id == group.id
        ).order_by(GroupMember.joined_at.desc()).limit(2).all()
        
        member_avatars = []
        for m in recent_members:
            u = db.query(User).filter(User.id == m.user_id).first()
            if u:
                member_avatars.append({
                    "avatar_url": u.avatar_url,
                    "full_name": u.full_name or u.username,
                })
        
        result.append({
            "id": str(group.id),
            "group_name": group.group_name,
            "group_type": group.group_type,
            "is_public": group.is_public,
            "join_code": group.join_code,
            "description": group.description,
            "member_count": group.member_count,
            "created_by": str(group.created_by) if group.created_by else None,
            "created_at": group.created_at.isoformat() if group.created_at else None,
            "updated_at": group.updated_at.isoformat() if group.updated_at else None,
            "member_avatars": member_avatars,
        })
    
    return result


# ============================================
# Create group
# ============================================
@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    request: GroupCreateRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Tạo group mới
    """
    new_group = Group(
        group_name=request.group_name,
        group_type=request.group_type,
        is_public=request.is_public,
        description=request.description,
        created_by=current_user.id,
        member_count=1
    )
    
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    
    # Thêm creator vào group
    creator_member = GroupMember(
        group_id=new_group.id,
        user_id=current_user.id,
        role="owner"
    )
    
    db.add(creator_member)
    db.commit()
    
    return new_group


# ============================================
# Get group detail
# ============================================
@router.get("/{group_id}", response_model=GroupDetailResponse)
async def get_group(
    group_id: UUID,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Lấy chi tiết group
    """
    group = db.query(Group).filter(
        Group.id == group_id
    ).first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Kiểm tra user có quyền truy cập
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == current_user.id
    ).first()
    
    if not member and not group.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this group"
        )
    
    return group


# ============================================
# Update group
# ============================================
@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: UUID,
    request: GroupUpdateRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Cập nhật group
    """
    group = db.query(Group).filter(
        Group.id == group_id
    ).first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Kiểm tra user có quyền
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == current_user.id
    ).first()
    
    if not member or member.role not in ["owner", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this group"
        )
    
    # Cập nhật fields
    if request.group_name is not None:
        group.group_name = request.group_name
    if request.description is not None:
        group.description = request.description
    if request.is_public is not None:
        group.is_public = request.is_public
    
    db.commit()
    db.refresh(group)
    
    return group


# ============================================
# Add member to group
# ============================================
@router.post("/{group_id}/members", status_code=status.HTTP_201_CREATED)
async def add_group_member(
    group_id: UUID,
    request: GroupMemberAddRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Thêm member vào group
    """
    group = db.query(Group).filter(
        Group.id == group_id
    ).first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Kiểm tra user có quyền
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == current_user.id
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a member of this group to add members"
        )
    
    # Kiểm tra user được thêm tồn tại
    target_user = db.query(User).filter(
        User.id == request.user_id
    ).first()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Kiểm tra đã là member chưa
    existing_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == request.user_id
    ).first()
    
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this group"
        )
    
    # Thêm member
    new_member = GroupMember(
        group_id=group_id,
        user_id=request.user_id,
        role="member"
    )
    
    db.add(new_member)
    group.member_count += 1
    
    db.commit()
    
    return {"message": "Member added successfully"}


# ============================================
# List group members
# ============================================
@router.get("/{group_id}/members")
async def list_group_members(
    group_id: UUID,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Lấy danh sách thành viên của group
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    # Kiểm tra user là member
    is_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == current_user.id
    ).first()
    if not is_member and not group.is_public:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
    result = []
    for m in members:
        user = db.query(User).filter(User.id == m.user_id).first()
        result.append({
            "id": str(m.id),
            "group_id": str(m.group_id),
            "user_id": str(m.user_id),
            "role": m.role,
            "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            "user": {
                "id": str(user.id),
                "username": user.username,
                "full_name": user.full_name,
                "avatar_url": user.avatar_url,
                "student_id": user.student_id,
            } if user else None,
        })
    return result


# ============================================
# Send group message
# ============================================
@router.post("/{group_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_group_message(
    group_id: UUID,
    request: GroupMessageCreateRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Gửi tin nhắn trong group
    """
    group = db.query(Group).filter(
        Group.id == group_id
    ).first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Kiểm tra user là member
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == current_user.id
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group"
        )
    
    # Tạo message
    new_message = GroupMessage(
        group_id=group_id,
        user_id=current_user.id,
        message_type=request.message_type,
        content=request.content
    )
    
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    
    return {"message": "Message sent successfully", "data": new_message}


# ============================================
# Delete group
# ============================================
@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: UUID,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Xóa group
    """
    group = db.query(Group).filter(
        Group.id == group_id
    ).first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Kiểm tra user là owner
    if group.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only group owner can delete the group"
        )
    
    db.delete(group)
    db.commit()


# ============================================
# Leave group
# ============================================
@router.post("/{group_id}/leave")
async def leave_group(
    group_id: UUID,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Rời khỏi group
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == current_user.id
    ).first()

    if not member:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You are not a member of this group")

    if group.created_by == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group owner cannot leave. Delete the group instead.")

    db.delete(member)
    group.member_count = max(0, (group.member_count or 1) - 1)

    # Add system message
    system_msg = GroupMessage(
        group_id=group_id,
        user_id=current_user.id,
        message_type="system",
        content=f"{current_user.full_name or current_user.username} đã rời khỏi nhóm",
    )
    db.add(system_msg)

    db.commit()

    return {"message": "Left group successfully"}
