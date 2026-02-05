"""
Quản lý kết nối Redis cho Token Blacklist
"""
import redis.asyncio as redis
from typing import Optional
from datetime import timedelta

from .config import settings


class RedisBlacklistManager:
    """
    Quản lý blacklist tokens trên Redis
    
    Sử dụng để lưu access_token và refresh_token bị logout
    để ngăn chúng được sử dụng lại
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
    
    async def connect(self):
        """
        Kết nối tới Redis server
        """
        self.redis_client = await redis.from_url(
            settings.REDIS_URL,
            db=settings.REDIS_BLACKLIST_DB,
            encoding="utf8",
            decode_responses=True,
        )
    
    async def disconnect(self):
        """
        Ngắt kết nối Redis
        """
        if self.redis_client:
            await self.redis_client.close()
    
    async def add_to_blacklist(
        self,
        token: str,
        ttl: timedelta,
    ) -> bool:
        """
        Thêm token vào blacklist
        
        Args:
            token: JWT token cần blacklist
            ttl: Thời gian tồn tại trong Redis
        
        Returns:
            True nếu thêm thành công, False nếu thất bại
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")
        
        key = f"blacklist:{token}"
        try:
            await self.redis_client.setex(
                key,
                int(ttl.total_seconds()),
                "blacklisted"
            )
            return True
        except Exception as e:
            print(f"Error adding token to blacklist: {e}")
            return False
    
    async def is_blacklisted(self, token: str) -> bool:
        """
        Kiểm tra token có bị blacklist không
        
        Args:
            token: JWT token cần kiểm tra
        
        Returns:
            True nếu token bị blacklist, False nếu không
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")
        
        key = f"blacklist:{token}"
        try:
            result = await self.redis_client.exists(key)
            return bool(result)
        except Exception as e:
            print(f"Error checking token blacklist: {e}")
            return False
    
    async def remove_from_blacklist(self, token: str) -> bool:
        """
        Xóa token khỏi blacklist (nếu cần)
        
        Args:
            token: JWT token cần xóa
        
        Returns:
            True nếu xóa thành công
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")
        
        key = f"blacklist:{token}"
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Error removing token from blacklist: {e}")
            return False
    
    async def get_ttl(self, token: str) -> int:
        """
        Lấy thời gian sống còn lại của token trong blacklist
        
        Args:
            token: JWT token
        
        Returns:
            TTL in seconds, -1 nếu không tìm thấy
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")
        
        key = f"blacklist:{token}"
        try:
            ttl = await self.redis_client.ttl(key)
            return ttl
        except Exception as e:
            print(f"Error getting token TTL: {e}")
            return -1


# Global Redis blacklist manager instance
redis_blacklist = RedisBlacklistManager()
