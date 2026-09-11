from pathlib import Path
from django.conf import settings
from django.core.files.storage import FileSystemStorage, storages


def product_photo_storage():
    """Use configured storage, with a safe local media directory for development."""
    backend = settings.STORAGES.get('default', {}).get('BACKEND', '')
    if backend and backend != 'django.core.files.storage.FileSystemStorage':
        return storages['default']
    if settings.MEDIA_ROOT:
        return storages['default']
    return FileSystemStorage(location=Path(settings.BASE_DIR) / 'media')
