"""
Group Service - Business Logic Layer
Xử lý các nghiệp vụ liên quan đến groups: CRUD, members, messages
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, status

from models.groups import Group, GroupMember, GroupMessage, GroupFile
from models.users import User


class GroupService:
    """
    Service xử lý business logic cho groups
    """
    
    @staticmethod
    def create_group(
        creator_id: str,
        group_name: str,
        group_type: str,
        is_public: bool,
        description: Optional[str],
        db: Session
    ) -> Group:
        """
        Tạo group mới
        
        Args:
            creator_id: ID của user tạo group
            group_name: Tên group
            group_type: Loại group (study/project/social)
            is_public: Group công khai hay không
            description: Mô tả group
            db: Database session
        
        Returns:
            Group object mới
        """
        new_group = Group(
            group_name=group_name,
            group_type=group_type,
            is_public=is_public,
            description=description,
            created_by=creator_id,
            member_count=1
        )
        
        db.add(new_group)
        db.commit()
        db.refresh(new_group)
        
        # Thêm creator vào group với role owner
        creator_member = GroupMember(
            group_id=new_group.id,
            user_id=creator_id,
            role="owner"
        )
        
        db.add(creator_member)
        db.commit()
        
        return new_group
    
    @staticmethod
    def get_user_groups(
        user_id: str,
        db: Session,
        skip: int = 0,
        limit: int = 10
    ) -> List[Group]:
        """
        Lấy danh sách groups mà user tham gia
        
        Args:
            user_id: ID của user
            db: Database session
            skip: Số lượng bỏ qua (pagination)
            limit: Số lượng tối đa (pagination)
        
        Returns:
            List of Group objects
        """
        member_groups = db.query(Group).join(GroupMember).filter(
            GroupMember.user_id == user_id
        ).offset(skip).limit(limit).all()
        
        return member_groups
    
    @staticmethod
    def get_group_by_id(
        group_id: UUID,
        user_id: str,
        db: Session
    ) -> Group:
        """
        Lấy chi tiết group
        
        Args:
            group_id: ID của group
            user_id: ID của user (để check quyền)
            db: Database session
        
        Returns:
            Group object
        
        Raises:
            HTTPException: Nếu group không tồn tại hoặc user không có quyền
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
            GroupMember.user_id == user_id
        ).first()
        
        if not member and not group.is_public:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this group"
            )
        
        return group
    
    @staticmethod
    def update_group(
        group_id: UUID,
        user_id: str,
        group_name: Optional[str],
        description: Optional[str],
        is_public: Optional[bool],
        db: Session
    ) -> Group:
        """
        Cập nhật group (chỉ owner/admin)
        
        Args:
            group_id: ID của group
            user_id: ID của user (để check quyền)
            group_name: Tên group mới
            description: Mô tả mới
            is_public: Public status mới
            db: Database session
        
        Returns:
            Group object đã cập nhật
        
        Raises:
            HTTPException: Nếu group không tồn tại hoặc user không có quyền
        """
        group = db.query(Group).filter(
            Group.id == group_id
        ).first()
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        # Kiểm tra user có quyền (owner hoặc admin)
        member = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        ).first()
        
        if not member or member.role not in ["owner", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this group"
            )
        
        # Cập nhật fields
        if group_name is not None:
            group.group_name = group_name
        if description is not None:
            group.description = description
        if is_public is not None:
            group.is_public = is_public
        
        db.commit()
        db.refresh(group)
        
        return group
    
    @staticmethod
    def add_member_to_group(
        group_id: UUID,
        requester_id: str,
        target_user_id: str,
        db: Session
    ) -> GroupMember:
        """
        Thêm member vào group (chỉ owner/admin)
        
        Args:
            group_id: ID của group
            requester_id: ID của user yêu cầu thêm member
            target_user_id: ID của user được thêm
            db: Database session
        
        Returns:
            GroupMember object mới
        
        Raises:
            HTTPException: Nếu không có quyền hoặc user đã là member
        """
        group = db.query(Group).filter(
            Group.id == group_id
        ).first()
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found"
            )
        
        # Kiểm tra requester có quyền (owner hoặc admin)
        requester_member = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == requester_id
        ).first()
        
        if not requester_member or requester_member.role not in ["owner", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to add members to this group"
            )
        
        # Kiểm tra target user tồn tại
        target_user = db.query(User).filter(
            User.id == target_user_id
        ).first()
        
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Kiểm tra đã là member chưa
        existing_member = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == target_user_id
        ).first()
        
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this group"
            )
        
        # Thêm member
        new_member = GroupMember(
            group_id=group_id,
            user_id=target_user_id,
            role="member"
        )
        
        db.add(new_member)
        group.member_count += 1
        
        db.commit()
        db.refresh(new_member)
        
        return new_member
    
    @staticmethod
    def send_group_message(
        group_id: UUID,
        user_id: str,
        message_type: str,
        content: str,
        db: Session
    ) -> GroupMessage:
        """
        Gửi tin nhắn trong group
        
        Args:
            group_id: ID của group
            user_id: ID của user gửi message
            message_type: Loại message (text/file/system)
            content: Nội dung message
            db: Database session
        
        Returns:
            GroupMessage object mới
        
        Raises:
            HTTPException: Nếu group không tồn tại hoặc user không phải member
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
            GroupMember.user_id == user_id
        ).first()
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this group"
            )
        
        # Tạo message
        new_message = GroupMessage(
            group_id=group_id,
            user_id=user_id,
            message_type=message_type,
            content=content
        )
        
        db.add(new_message)
        db.commit()
        db.refresh(new_message)
        
        return new_message
    
    @staticmethod
    def delete_group(
        group_id: UUID,
        user_id: str,
        db: Session
    ) -> bool:
        """
        Xóa group (chỉ owner)
        
        Args:
            group_id: ID của group
            user_id: ID của user (để check quyền)
            db: Database session
        
        Returns:
            True nếu xóa thành công
        
        Raises:
            HTTPException: Nếu group không tồn tại hoặc user không phải owner
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
        if group.created_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only group owner can delete the group"
            )
        
        db.delete(group)
        db.commit()
        
        return True


# Global group service instance
group_service = GroupService()
