"""Decode real images, normalize orientation and discard source metadata."""
from io import BytesIO
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 32_000_000


def normalize_photo(upload):
    if not upload or not upload.size or upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError({'image': 'Choose one photo no larger than 20 MB.'})
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            upload.seek(0)
            with Image.open(upload) as source:
                if source.format not in {'JPEG', 'PNG', 'WEBP', 'HEIF', 'HEIC'}:
                    raise ValidationError({'image': 'Use a JPEG, PNG, WebP or HEIC photograph.'})
                if source.width * source.height > MAX_PIXELS:
                    raise ValidationError({'image': 'Photo exceeds 32 megapixels. Use a lower camera resolution.'})
                if getattr(source, 'n_frames', 1) > 1:
                    raise ValidationError({'image': 'Choose a still photo rather than an animated or multi-image file.'})
                source.load()
                oriented = ImageOps.exif_transpose(source)
                oriented.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
                rgba = oriented.convert('RGBA')
                clean = Image.new('RGB', rgba.size, 'white')
                clean.paste(rgba, mask=rgba.getchannel('A'))
                result = BytesIO()
                clean.save(result, format='JPEG', quality=90, optimize=True)
                return result.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValidationError({'image': 'The photo could not be read. Try a new photo or a JPEG file.'}) from exc
