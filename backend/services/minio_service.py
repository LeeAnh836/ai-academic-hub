"""
MinIO Service - Business Logic Layer
Xử lý các nghiệp vụ liên quan đến object storage: upload, download, delete files
"""
from minio.error import S3Error
from typing import BinaryIO, Optional
from datetime import timedelta
import uuid
import os

from core.minio import minio_client
from core.config import settings


class MinIOService:
    """
    Service xử lý business logic cho MinIO object storage
    """
    
    @staticmethod
    def upload_file(
        file_data: bytes,
        file_name: str,
        content_type: str,
        user_id: str,
        bucket_name: str = None
    ) -> dict:
        """
        Upload file lên MinIO
        
        Args:
            file_data: File binary data (bytes)
            file_name: Tên file gốc
            content_type: MIME type của file
            user_id: ID của user (để tạo folder structure)
            bucket_name: Tên bucket (mặc định lấy từ settings)
        
        Returns:
            dict: {
                "object_name": str,  # Tên object trong MinIO
                "file_path": str,    # Full path
                "bucket": str,       # Bucket name
                "size": int          # File size in bytes
            }
        
        Raises:
            Exception: Nếu upload thất bại
        """
        bucket = bucket_name or settings.MINIO_BUCKET_NAME
        
        try:
            # Tạo object name với structure: user_id/uuid_filename
            file_extension = os.path.splitext(file_name)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            object_name = f"{user_id}/{unique_filename}"
            
            # Convert bytes to BytesIO for MinIO
            from io import BytesIO
            file_io = BytesIO(file_data)
            file_size = len(file_data)
            
            # Upload to MinIO
            minio_client.client.put_object(
                bucket_name=bucket,
                object_name=object_name,
                data=file_io,
                length=file_size,
                content_type=content_type
            )
            
            return {
                "object_name": object_name,
                "file_path": f"{bucket}/{object_name}",
                "bucket": bucket,
                "size": file_size
            }
        
        except S3Error as e:
            raise Exception(f"MinIO upload error: {e}")
    
    @staticmethod
    def upload_file_bytes(
        file_content: bytes,
        object_name: str,
        content_type: str,
        bucket_name: str = None
    ) -> str:
        """
        Upload file bytes lên MinIO và trả về URL public
        
        Args:
            file_content: File binary data (bytes)
            object_name: Tên object trong MinIO (vd: avatars/user_id.jpg)
            content_type: MIME type của file
            bucket_name: Tên bucket (mặc định lấy từ settings)
        
        Returns:
            str: Public URL của file
        
        Raises:
            Exception: Nếu upload thất bại
        """
        bucket = bucket_name or settings.MINIO_BUCKET_NAME
        
        try:
            # Convert bytes to BytesIO for MinIO
            from io import BytesIO
            file_io = BytesIO(file_content)
            file_size = len(file_content)
            
            # Upload to MinIO
            minio_client.client.put_object(
                bucket_name=bucket,
                object_name=object_name,
                data=file_io,
                length=file_size,
                content_type=content_type
            )
            
            # Return public URL
            # Format: http://minio:9000/bucket/object_name
            minio_url = settings.MINIO_URL.rstrip('/')
            return f"{minio_url}/{bucket}/{object_name}"
        
        except S3Error as e:
            raise Exception(f"MinIO upload error: {e}")
    
    @staticmethod
    def download_file(
        object_name: str,
        bucket_name: str = None
    ) -> bytes:
        """
        Download file từ MinIO
        
        Args:
            object_name: Tên object trong MinIO
            bucket_name: Tên bucket (mặc định lấy từ settings)
        
        Returns:
            bytes: File data
        
        Raises:
            Exception: Nếu download thất bại
        """
        bucket = bucket_name or settings.MINIO_BUCKET_NAME
        
        try:
            response = minio_client.client.get_object(
                bucket_name=bucket,
                object_name=object_name
            )
            
            data = response.read()
            response.close()
            response.release_conn()
            
            return data
        
        except S3Error as e:
            raise Exception(f"MinIO download error: {e}")
    
    @staticmethod
    def delete_file(
        object_name: str,
        bucket_name: str = None
    ) -> bool:
        """
        Xóa file từ MinIO
        
        Args:
            object_name: Tên object trong MinIO
            bucket_name: Tên bucket (mặc định lấy từ settings)
        
        Returns:
            bool: True nếu xóa thành công
        
        Raises:
            Exception: Nếu xóa thất bại
        """
        bucket = bucket_name or settings.MINIO_BUCKET_NAME
        
        try:
            minio_client.client.remove_object(
                bucket_name=bucket,
                object_name=object_name
            )
            return True
        
        except S3Error as e:
            raise Exception(f"MinIO delete error: {e}")
    
    @staticmethod
    def get_presigned_url(
        object_name: str,
        bucket_name: str = None,
        expires: timedelta = timedelta(hours=1)
    ) -> str:
        """
        Tạo presigned URL để download file (temporary access)
        
        Args:
            object_name: Tên object trong MinIO
            bucket_name: Tên bucket (mặc định lấy từ settings)
            expires: Thời gian hết hạn của URL
        
        Returns:
            str: Presigned URL
        
        Raises:
            Exception: Nếu tạo URL thất bại
        """
        bucket = bucket_name or settings.MINIO_BUCKET_NAME
        
        try:
            url = minio_client.client.presigned_get_object(
                bucket_name=bucket,
                object_name=object_name,
                expires=expires
            )
            return url
        
        except S3Error as e:
            raise Exception(f"MinIO presigned URL error: {e}")


# Global instance
minio_service = MinIOService()
