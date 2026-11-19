#!/usr/bin/env python3
"""
Migration script: Upload hedgehog images from filesystem to MongoDB GridFS.

Usage:
    python scripts/migrate_hedgehog_images.py
"""
import asyncio
import hashlib
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infra.mongo.client import MongoClient
from src.services.hedgehog_gridfs import HedgehogGridFS
from src.core.config import settings


async def migrate_images():
    """Upload all hedgehog images from filesystem to GridFS."""
    # Source directory
    source_dir = Path(settings.BASE_DIR) / 'src/infra/storage/ega'

    if not source_dir.exists():
        print(f"❌ Source directory not found: {source_dir}")
        return

    # Get all image files
    image_files = sorted(
        f for f in source_dir.iterdir()
        if f.is_file() and f.suffix.lower() in {'.jpg', '.jpeg', '.png'}
    )

    if not image_files:
        print("❌ No image files found in source directory")
        return

    print(f"📁 Found {len(image_files)} images to migrate")

    # Connect to MongoDB
    mongo = MongoClient()
    await mongo.connect()
    print("✅ Connected to MongoDB")

    # Create GridFS service
    gridfs = HedgehogGridFS(mongo)

    # Check existing images in GridFS
    existing_count = await gridfs.count_images()
    print(f"📊 Existing images in GridFS: {existing_count}")

    # Get list of existing filenames to skip duplicates
    existing_files = await gridfs.list_images()
    existing_names = {f['filename'] for f in existing_files}

    # Migrate each image
    uploaded = 0
    skipped = 0
    errors = 0

    for i, img_path in enumerate(image_files, 1):
        filename = img_path.name

        if filename in existing_names:
            skipped += 1
            if skipped % 50 == 0:
                print(f"  ⏭️  Skipped {skipped} existing files...")
            continue

        try:
            # Read image content
            content = img_path.read_bytes()

            # Compute hash for metadata
            file_hash = hashlib.sha256(content).hexdigest()[:16]

            # Upload to GridFS
            file_id = await gridfs.upload_image(
                filename=filename,
                content=content,
                metadata={
                    "sha256": file_hash,
                    "size": len(content),
                    "original_path": str(img_path),
                    "migrated": True
                }
            )

            uploaded += 1

            # Progress
            if uploaded % 50 == 0 or i == len(image_files):
                print(f"  📤 Uploaded {uploaded}/{len(image_files)} (skipped: {skipped}, errors: {errors})")

        except Exception as e:
            errors += 1
            print(f"  ❌ Error uploading {filename}: {e}")

    # Final stats
    final_count = await gridfs.count_images()
    print(f"\n✅ Migration complete!")
    print(f"   Total in GridFS: {final_count}")
    print(f"   Uploaded: {uploaded}")
    print(f"   Skipped (duplicates): {skipped}")
    print(f"   Errors: {errors}")

    await mongo.close()


if __name__ == "__main__":
    asyncio.run(migrate_images())