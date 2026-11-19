"""
GridFS service for hedgehog daily images.
Stores and retrieves hedgehog photos from MongoDB GridFS.
"""
import io
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from bson import ObjectId

from src.infra.mongo.client import MongoClient


class HedgehogGridFS:
    """GridFS wrapper for hedgehog daily images."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self._bucket: Optional[AsyncIOMotorGridFSBucket] = None

    @property
    def bucket(self) -> AsyncIOMotorGridFSBucket:
        if self._bucket is None:
            self._bucket = AsyncIOMotorGridFSBucket(
                self.mongo_client.database,
                bucket_name="hedgehog_images"
            )
        return self._bucket

    async def upload_image(self, filename: str, content: bytes, metadata: dict = None) -> ObjectId:
        """Upload an image to GridFS. Returns the ObjectId."""
        upload_stream = self.bucket.open_upload_stream(
            filename,
            metadata=metadata or {}
        )
        await upload_stream.write(content)
        await upload_stream.close()
        return upload_stream._id

    async def get_image(self, filename: str) -> Optional[bytes]:
        """Retrieve image by filename. Returns bytes or None if not found."""
        try:
            download_stream = await self.bucket.open_download_stream_by_name(filename)
            content = await download_stream.read()
            return content
        except Exception:
            return None

    async def get_image_by_id(self, file_id: ObjectId) -> Optional[bytes]:
        """Retrieve image by ObjectId. Returns bytes or None if not found."""
        try:
            download_stream = await self.bucket.open_download_stream(file_id)
            content = await download_stream.read()
            return content
        except Exception:
            return None

    async def list_images(self) -> List[dict]:
        """List all images in the bucket."""
        cursor = self.bucket.find({})
        files = []
        async for file in cursor:
            files.append({
                "id": file._id,
                "filename": file.filename,
                "length": file.length,
                "upload_date": file.upload_date,
                "metadata": file.metadata
            })
        return files

    async def delete_image(self, filename: str) -> bool:
        """Delete image by filename."""
        try:
            # Find file by name first
            cursor = self.bucket.find({"filename": filename})
            async for file in cursor:
                await self.bucket.delete(file._id)
                return True
        except Exception:
            pass
        return False

    async def get_random_image(self) -> Optional[dict]:
        """Get a random image from the bucket. Returns file info dict."""
        import random
        files = await self.list_images()
        if not files:
            return None
        return random.choice(files)

    async def count_images(self) -> int:
        """Count total images in bucket."""
        count = 0
        cursor = self.bucket.find({})
        async for _ in cursor:
            count += 1
        return count