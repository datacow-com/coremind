import os
from abc import ABC, abstractmethod
from typing import BinaryIO, Generator, Optional

import aiofiles
from server.config import settings

class BlobStorage(ABC):
    @abstractmethod
    async def put(self, path: str, content: bytes) -> str:
        """Write bytes to storage"""
        pass

    @abstractmethod
    async def get(self, path: str) -> bytes:
        """Read bytes from storage"""
        pass

    @abstractmethod
    async def stream_get(self, path: str, chunk_size: int = 1024 * 1024) -> Generator[bytes, None, None]:
        """Stream read bytes from storage"""
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if file exists"""
        pass

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete file"""
        pass

class LocalBlobStorage(BlobStorage):
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def _resolve(self, path: str) -> str:
        return os.path.join(self.base_dir, path)

    async def put(self, path: str, content: bytes) -> str:
        full_path = self._resolve(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        async with aiofiles.open(full_path, "wb") as f:
            await f.write(content)
        return full_path

    async def get(self, path: str) -> bytes:
        full_path = self._resolve(path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"{path} not found")
        async with aiofiles.open(full_path, "rb") as f:
            return await f.read()

    async def stream_get(self, path: str, chunk_size: int = 1024 * 1024):
        full_path = self._resolve(path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"{path} not found")
        async with aiofiles.open(full_path, "rb") as f:
            while chunk := await f.read(chunk_size):
                yield chunk

    async def exists(self, path: str) -> bool:
        return os.path.exists(self._resolve(path))

    async def delete(self, path: str) -> None:
        full_path = self._resolve(path)
        if os.path.exists(full_path):
            os.remove(full_path)

class OSSBlobStorage(BlobStorage):
    """Aliyun OSS implementation"""
    def __init__(self):
        try:
            import oss2
        except ImportError:
            raise ImportError("oss2 package is required for OSSBlobStorage")
        
        access_key_id = os.environ.get("OSS_ACCESS_KEY_ID")
        access_key_secret = os.environ.get("OSS_ACCESS_KEY_SECRET")
        endpoint = os.environ.get("OSS_ENDPOINT")
        bucket_name = os.environ.get("OSS_BUCKET")
        
        if not all([access_key_id, access_key_secret, endpoint, bucket_name]):
            raise ValueError("OSS configuration missing in environment variables")
            
        self.auth = oss2.Auth(access_key_id, access_key_secret)
        self.bucket = oss2.Bucket(self.auth, endpoint, bucket_name)

    async def put(self, path: str, content: bytes) -> str:
        # oss2 is sync, wrap in executor if needed for high throughput
        # For simplicity in mvp, using it directly or we can use asyncio.to_thread
        import asyncio
        await asyncio.to_thread(self.bucket.put_object, path, content)
        return f"oss://{self.bucket.bucket_name}/{path}"

    async def get(self, path: str) -> bytes:
        import asyncio
        result = await asyncio.to_thread(self.bucket.get_object, path)
        return result.read()

    async def stream_get(self, path: str, chunk_size: int = 1024 * 1024):
        # This needs careful implementation for async streaming from sync lib
        # Fallback to full read for now or use an async oss lib if available
        data = await self.get(path)
        for i in range(0, len(data), chunk_size):
            yield data[i:i+chunk_size]

    async def exists(self, path: str) -> bool:
        import asyncio
        return await asyncio.to_thread(self.bucket.object_exists, path)

    async def delete(self, path: str) -> None:
        import asyncio
        await asyncio.to_thread(self.bucket.delete_object, path)

class MinIOBlobStorage(BlobStorage):
    """MinIO / S3 implementation"""
    def __init__(self):
        try:
            from minio import Minio
        except ImportError:
            raise ImportError("minio package is required for MinIOBlobStorage")
            
        endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
        access_key = os.environ.get("MINIO_ROOT_USER", "minioadmin")
        secret_key = os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin")
        self.bucket_name = os.environ.get("MINIO_BUCKET", "omnirag")
        secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"
        
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)

    async def put(self, path: str, content: bytes) -> str:
        import io
        import asyncio
        stream = io.BytesIO(content)
        await asyncio.to_thread(
            self.client.put_object,
            self.bucket_name,
            path,
            stream,
            length=len(content)
        )
        return f"minio://{self.bucket_name}/{path}"

    async def get(self, path: str) -> bytes:
        import asyncio
        resp = await asyncio.to_thread(self.client.get_object, self.bucket_name, path)
        try:
            return resp.read()
        finally:
            resp.close()
            
    async def stream_get(self, path: str, chunk_size: int = 1024 * 1024):
        import asyncio
        # Minio response is a stream
        resp = await asyncio.to_thread(self.client.get_object, self.bucket_name, path)
        try:
            # This is a blocking stream from minio, wrapping it perfectly in async generator 
            # requires running the read in thread pool per chunk or reading all.
            # For true async, consider aiobotocore.
            # For now, simple blocking read in chunks (not ideal for event loop but works for low concurrency)
            for chunk in resp.stream(chunk_size):
                yield chunk
        finally:
            resp.close()

    async def exists(self, path: str) -> bool:
        import asyncio
        try:
            await asyncio.to_thread(self.client.stat_object, self.bucket_name, path)
            return True
        except Exception:
            return False

    async def delete(self, path: str) -> None:
        import asyncio
        await asyncio.to_thread(self.client.remove_object, self.bucket_name, path)


_BLOB_STORE: Optional[BlobStorage] = None

def get_blob_store() -> BlobStorage:
    global _BLOB_STORE
    if _BLOB_STORE:
        return _BLOB_STORE
        
    store_type = os.environ.get("BLOB_STORE_TYPE", "local").lower()
    
    if store_type == "oss":
        _BLOB_STORE = OSSBlobStorage()
    elif store_type == "minio":
        _BLOB_STORE = MinIOBlobStorage()
    else:
        _BLOB_STORE = LocalBlobStorage(settings.uploads_dir_resolved)
        
    return _BLOB_STORE

