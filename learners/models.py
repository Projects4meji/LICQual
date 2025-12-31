# learners/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.utils.text import slugify
import secrets


def certificate_upload_to(instance, filename: str) -> str:
    """
    Store files at: <email>/<name>/<16digit-random>/<original_filename>
    Works for S3-compatible backends (e.g., DigitalOcean Spaces).
    """
    # Email folder (safe and lowercase)
    email = (instance.owner.email or "unknown").strip().lower().replace("/", "_").replace("@", "_at_")


    # Human-readable name folder; fallback to email local-part
    base_name = (instance.owner.full_name or (instance.owner.email.split("@")[0] if instance.owner.email else "user")).strip()
    name = slugify(base_name) or "user"

    # 16-digit numeric random folder (digits only)
    rand16 = "".join(secrets.choice("0123456789") for _ in range(16))

    # Keep the original file name at the leaf
    return f"{email}/{name}/{rand16}/{filename}"

class LearnerCertificate(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uploaded_certificates",
    )
    title = models.CharField(max_length=255)
    issuing_body = models.CharField(max_length=255)
    issue_date = models.DateField()
    expiry_date = models.DateField(blank=True, null=True)
    file = models.FileField(
        upload_to=certificate_upload_to,
        validators=[FileExtensionValidator(["png", "jpg", "jpeg", "pdf"])],
        help_text="PNG, JPG, or PDF"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_active(self) -> bool:
        """Active if no expiry or expiry date is today/in the future."""
        if not self.expiry_date:
            return True
        # Use local date for intuitive behaviour
        return self.expiry_date >= timezone.localdate()

    def __str__(self):
        return f"{self.title} • {self.owner.email}"
