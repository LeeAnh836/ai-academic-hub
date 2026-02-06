"""
MinIO Client - Object Storage Connection
Quản lý kết nối tới MinIO S3-compatible storage
"""
from minio import Minio
from minio.error import S3Error
from core.config import settings


class MinIOClient:
    """
    Singleton MinIO client để quản lý kết nối
    """
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MinIOClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Khởi tạo MinIO client"""
        if self._client is None:
            self._client = Minio(
                endpoint=settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE
            )
            print(f"✅ MinIO client initialized: {settings.MINIO_ENDPOINT}")
    
    @property
    def client(self) -> Minio:
        """Lấy MinIO client instance"""
        return self._client
    
    async def ensure_bucket_exists(self, bucket_name: str = None) -> bool:
        """
        Đảm bảo bucket tồn tại, nếu không thì tạo mới
        
        Args:
            bucket_name: Tên bucket (mặc định lấy từ settings)
        
        Returns:
            True nếu bucket tồn tại hoặc tạo thành công
        """
        bucket = bucket_name or settings.MINIO_BUCKET_NAME
        
        try:
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)
                print(f"✅ MinIO bucket created: {bucket}")
            return True
        except S3Error as e:
            print(f"❌ MinIO bucket error: {e}")
            return False
    
    async def connect(self):
        """Kết nối và setup bucket"""
        await self.ensure_bucket_exists()
    
    async def disconnect(self):
        """Ngắt kết nối (MinIO không cần close connection)"""
        print("✅ MinIO client closed")


# Global instance
minio_client = MinIOClient()
