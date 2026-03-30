# backend/app/utils/supabase_client.py
"""
Supabase Storage client wrapper untuk download files
"""
import os
import logging
from typing import Optional
import requests

from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)



class SupabaseStorageClient:
    """
    Client untuk interact dengan Supabase Storage
    """
    
    def __init__(
        self,
        url: str = None,
        key: str = None,
        bucket_name: str = None
    ):
        """
        Initialize Supabase Storage client
        
        Args:
            url: Supabase project URL (e.g., https://hnspszhnpbshkvseemrb.supabase.co)
            key: Supabase anon key
            bucket_name: Storage bucket name (default: "payslips")
        """
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_KEY")
        self.bucket_name = bucket_name or os.getenv("SUPABASE_STORAGE_BUCKET", "payslips")
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL dan SUPABASE_KEY harus diset di .env")
        
        # Build API endpoint
        self.base_url = f"{self.url}/storage/v1"
        self.headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/octet-stream"
        }
    
    def download_file(self, file_path: str) -> bytes:
        """
        Download file dari Supabase Storage
        
        Args:
            file_path: Path file di bucket (e.g., "uploads/2025-03/payroll.xlsx")
        
        Returns:
            File content sebagai bytes
        
        Raises:
            Exception: Jika file tidak ditemukan atau error network
        """
        try:
            url = f"{self.base_url}/object/public/{self.bucket_name}/{file_path}"
            
            logger.info(f"📥 Downloading file dari Supabase: {file_path}")
            
            response = requests.get(
                url,
                headers=self.headers,
                timeout=60
            )
            
            if response.status_code == 404:
                raise FileNotFoundError(f"File tidak ditemukan: {file_path}")
            
            if response.status_code != 200:
                raise Exception(f"Error download file: {response.status_code} - {response.text}")
            
            file_size = len(response.content)
            logger.info(f"✅ Downloaded {file_size} bytes from {file_path}")
            
            return response.content
        
        except Exception as e:
            logger.error(f"❌ Error downloading from Supabase: {str(e)}")
            raise
    
    def upload_file(
        self,
        file_path: str,
        file_content: bytes,
        content_type: str = "application/octet-stream",
        public: bool = False
    ) -> dict:
        """
        Upload file ke Supabase Storage
        
        Args:
            file_path: Path file di bucket (e.g., "uploads/payslips.zip")
            file_content: File content as bytes
            content_type: MIME type (default: application/octet-stream)
            public: Make file public accessible (default: False)
        
        Returns:
            Response dari Supabase dengan file metadata
        """
        try:
            url = f"{self.base_url}/object/{self.bucket_name}/{file_path}"
            
            headers = {
                "Authorization": f"Bearer {self.key}",
                "Content-Type": content_type,
                "x-upsert": "true"  # Overwrite if exists
            }
            
            logger.info(f"📤 Uploading file to Supabase: {file_path}")
            
            response = requests.post(
                url,
                data=file_content,
                headers=headers,
                timeout=60
            )
            
            if response.status_code not in [200, 201]:
                raise Exception(f"Error upload file: {response.status_code} - {response.text}")
            
            logger.info(f"✅ Uploaded {len(file_content)} bytes to {file_path}")
            
            return response.json()
        
        except Exception as e:
            logger.error(f"❌ Error uploading to Supabase: {str(e)}")
            raise
    
    def get_public_url(self, file_path: str) -> str:
        """
        Get public URL untuk file di Supabase Storage
        """
        return f"{self.url}/storage/v1/object/public/{self.bucket_name}/{file_path}"
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete file dari Supabase Storage
        
        Args:
            file_path: Path file di bucket
            
        Returns:
            True if successful
        """
        try:
            url = f"{self.base_url}/object/{self.bucket_name}/{file_path}"
            
            headers = {
                "Authorization": f"Bearer {self.key}"
            }
            
            logger.info(f"🗑️ Deleting file from Supabase: {file_path}")
            
            response = requests.delete(url, headers=headers, timeout=30)
            
            if response.status_code not in [200, 204, 404]:
                logger.warning(f"Delete returned {response.status_code}: {response.text}")
                return False
            
            logger.info(f"✅ Deleted file: {file_path}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Error deleting from Supabase: {str(e)}")
            return False


# Create singleton instance
supabase_storage = SupabaseStorageClient()