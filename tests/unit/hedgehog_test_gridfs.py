"""In-memory GridFS stand-in for tests; never used by the application."""
from io import BytesIO
from PIL import Image


class ImageStore:
    def __init__(self, images=None):
        if images is None:
            buf = BytesIO()
            Image.new('RGB', (64, 64), 'green').save(buf, format='JPEG')
            images = {'a.jpg': buf.getvalue(), 'b.jpg': buf.getvalue()}
        self.images = images

    async def list_images(self):
        return [{'id': name, 'filename': name} for name in sorted(self.images)]

    async def get_random_image(self):
        files = await self.list_images()
        return files[0] if files else None

    async def get_image(self, filename):
        return self.images.get(filename)

    async def get_image_by_id(self, file_id):
        return self.images.get(file_id)
