"""
Quản lý trạng thái online của user trên Redis
"""
import redis.asyncio as redis
from typing import Optional
from datetime import datetime, timezone

from core.config import settings


class UserPresenceManager:
    """
    Quản lý user online status trên Redis
    
    Dùng để tracking user hiện tại online hay không,
    lần hoạt động cuối cùng, vv
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.presence_db = 2  # Dùng DB khác với blacklist
    
    async def connect(self):
        """
        Kết nối tới Redis server
        """
        self.redis_client = await redis.from_url(
            settings.REDIS_URL,
            db=self.presence_db,
            encoding="utf8",
            decode_responses=True,
        )
    
    async def disconnect(self):
        """
        Ngắt kết nối Redis
        """
        if self.redis_client:
            await self.redis_client.close()
    
    async def mark_user_online(
        self,
        user_id: str,
        ttl: int = 3600
    ) -> bool:
        """
        Đánh dấu user online
        
        Args:
            user_id: ID của user
            ttl: Thời gian xem user vẫn online nếu không activity (default 1 giờ)
        
        Returns:
            True nếu thành công
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")
        
        key = f"user:online:{user_id}"
        try:
            await self.redis_client.setex(
                key,
                ttl,
                datetime.now(timezone.utc).isoformat()
            )
            return True
        except Exception as e:
            print(f"Error marking user online: {e}")
            return False
    
    async def is_user_online(self, user_id: str) -> bool:
        """
        Kiểm tra user có online không
        
        Args:
            user_id: ID của user
        
        Returns:
            True nếu user online, False nếu không
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")
        
        key = f"user:online:{user_id}"
        try:
            result = await self.redis_client.exists(key)
            return bool(result)
        except Exception as e:
            print(f"Error checking user online status: {e}")
            return False
    
    async def mark_user_offline(self, user_id: str) -> bool:
        """
        Xóa user khỏi online status (logout/disconnect)
        
        Args:
            user_id: ID của user
        
        Returns:
            True nếu xóa thành công
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")
        
        key = f"user:online:{user_id}"
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Error marking user offline: {e}")
            return False
    
    async def get_user_last_activity(self, user_id: str) -> Optional[datetime]:
        """
        Lấy thông tin hoạt động cuối cùng của user
        
        Args:
            user_id: ID của user
        
        Returns:
            DateTime của lần online cuối cùng, None nếu không online
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")
        
        key = f"user:online:{user_id}"
        try:
            result = await self.redis_client.get(key)
            if result:
                return datetime.fromisoformat(result)
            return None
        except Exception as e:
            print(f"Error getting user last activity: {e}")
            return None
    
    async def get_online_users(self) -> list[str]:
        """
        Lấy danh sách tất cả user đang online
        
        Returns:
            List chứa user_ids của những user online
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")
        
        try:
            keys = await self.redis_client.keys("user:online:*")
            # Extract user_id từ key format: user:online:{user_id}
            user_ids = [key.split(":")[-1] for key in keys]
            return user_ids
        except Exception as e:
            print(f"Error getting online users: {e}")
            return []
    
    async def get_online_users_count(self) -> int:
        """
        Lấy số lượng user đang online
        
        Returns:
            Số user online
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")
        
        try:
            count = await self.redis_client.dbsize()
            return count
        except Exception as e:
            print(f"Error getting online users count: {e}")
            return 0
    
    async def update_user_activity(self, user_id: str, ttl: int = 3600) -> bool:
        """
        Cập nhật thời gian hoạt động cuối cùng (refresh TTL)
        
        Args:
            user_id: ID của user
            ttl: Thời gian tồn tại (mặc định 1 giờ)
        
        Returns:
            True nếu cập nhật thành công
        """
        # Giống mark_user_online, nhưng có thể gọi lại mà không mất trạng thái
        return await self.mark_user_online(user_id, ttl)


# Global user presence manager instance
user_presence = UserPresenceManager()
