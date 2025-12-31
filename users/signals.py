# users/signals.py
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.db import transaction
from users.models import CustomUser

@receiver(pre_save, sender=CustomUser)
def _refresh_certs_on_name_change(sender, instance: CustomUser, **kwargs):
    # Only on update
    if not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    # If the name changed, regenerate after commit
    if (old.full_name or "").strip() != (instance.full_name or "").strip():
        def _regenerate():
            # Lazy import to avoid circulars at import time
            from superadmin.views import regenerate_certificates_for_user
            regenerate_certificates_for_user(instance)
        transaction.on_commit(_regenerate)
