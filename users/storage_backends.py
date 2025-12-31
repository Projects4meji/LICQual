# users/storage_backends.py
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from pathlib import Path

# Use S3 storage if USE_REMOTE_MEDIA is True, otherwise use local storage
USE_REMOTE = getattr(settings, 'USE_REMOTE_MEDIA', False)

if USE_REMOTE:
    try:
        from storages.backends.s3boto3 import S3Boto3Storage
        
        class MediaRootS3Boto3Storage(S3Boto3Storage):
            default_acl = "public-read"
            file_overwrite = False
            custom_domain = None  # let settings.AWS_S3_CUSTOM_DOMAIN handle host
        
        BaseStorage = MediaRootS3Boto3Storage
    except ImportError:
        # Fallback to local storage if storages is not installed
        USE_REMOTE = False

if not USE_REMOTE:
    # Use local file storage for development
    # Create a custom storage that respects the location parameter
    class LocalMediaStorage(FileSystemStorage):
        def __init__(self, location=None, base_url=None):
            if location:
                # Combine MEDIA_ROOT with the location subdirectory
                media_root = Path(settings.MEDIA_ROOT)
                full_location = media_root / location
                full_location.mkdir(parents=True, exist_ok=True)
                super().__init__(location=str(full_location), base_url=base_url)
            else:
                super().__init__(location=settings.MEDIA_ROOT, base_url=base_url)
    
    BaseStorage = LocalMediaStorage

class CertTemplateStorage(BaseStorage):
    location = "certificate_templates"

class CertSampleStorage(BaseStorage):
    location = "certificate_samples"

class CertOutputStorage(BaseStorage):
    location = "certificates"

class IsoTemplateStorage(BaseStorage):
    location = "iso_templates"

class IsoQrStorage(BaseStorage):
    location = "iso_qr"
