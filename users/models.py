from django.db import models, IntegrityError, transaction
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db.models.functions import Lower
import uuid
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, full_name='', **extra_fields):
        if not email:
            raise ValueError('The Email field must be set.')
        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, full_name='', **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, full_name, **extra_fields)
    
    @property
    def is_partner(self) -> bool:
        try:
            return self.roles.filter(name=Role.Names.PARTNER).exists()
        except Exception:
            return False

    @property
    def is_learner(self) -> bool:
        try:
            return self.roles.filter(name=Role.Names.LEARNER).exists()
        except Exception:
            return False



class Role(models.Model):
    class Names(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        PARTNER = 'partner', 'Partner'
        LEARNER = 'learner', 'Learner'

    name = models.CharField(max_length=20, choices=Names.choices, unique=True)

    def __str__(self):
        return self.get_name_display()


class CustomUser(AbstractUser):
    # Make it explicit for Django internals and admin
    EMAIL_FIELD = 'email'

    # Keep unique=True for friendly validation; DB constraint below enforces case-insensitive uniqueness
    email = models.EmailField(max_length=255, unique=True)
    full_name = models.CharField(max_length=150, blank=True)

    # We always generate a username before saving; allow blank in forms, not NULL in DB
    username = models.CharField(max_length=150, unique=True, blank=True)

    roles = models.ManyToManyField(Role, related_name='users', blank=True)

    # Use email as the login identifier
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    objects = CustomUserManager()
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    # Superadmin can lock profile so Partners cannot edit name/email
    is_profile_locked = models.BooleanField(
        default=False,
        help_text="When enabled, Partners cannot edit this user's name or email."
    )

    @property
    def is_partner(self) -> bool:
        return self.has_role(Role.Names.PARTNER)

    @property
    def is_learner(self) -> bool:
        return self.has_role(Role.Names.LEARNER)

    @property
    def avatar_safe_url(self) -> str:
        # safe to use in templates without raising when no file is set
        return self.avatar.url if self.avatar and self.avatar.name else ""
    
    @property
    def avatar_url(self) -> str:
        # Backwards-compatible alias used in some templates
        return self.avatar_safe_url



    class Meta:
        constraints = [
            # Case-insensitive uniqueness for email at the database level
            models.UniqueConstraint(
                Lower('email'),
                name='customuser_email_ci_unique',
            ),
        ]

    def has_role(self, role_name: str) -> bool:
        return self.roles.filter(name=role_name).exists()

    def save(self, *args, **kwargs):
        # Ensure a unique username is present for AbstractUser requirements
        if not self.username:
            base_username = (self.email.split('@', 1)[0] if self.email else 'user')[:30]

            def make_username():
                # 150 char limit; reserve 1 + 12 for "_" + suffix
                suffix = str(uuid.uuid4())[:12]
                candidate = f"{base_username}_{suffix}"
                if len(candidate) > 150:
                    candidate = f"{base_username[:(150 - 13)]}_{suffix}"
                return candidate

            for _ in range(5):
                self.username = make_username()
                try:
                    with transaction.atomic():
                        super().save(*args, **kwargs)
                    return  # success
                except IntegrityError:
                    # Collision on unique username, try again
                    continue
            raise ValueError("Unable to generate a unique username after multiple attempts.")

        # Username already set; normal save path
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name or self.email


class PasswordResetToken(models.Model):
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_valid(self) -> bool:
        return timezone.now() < self.expires_at

    def __str__(self):
        return f"PasswordResetToken<{self.user.email}>"


from django.db.models.signals import pre_save
from django.dispatch import receiver

@receiver(pre_save, sender=CustomUser)
def _rebuild_certs_if_name_changed(sender, instance, **kwargs):
    """
    If a user's full_name changed anywhere (admin or custom views),
    rebuild all issued certificates so the rendered name is current.
    """
    if not instance.pk:
        return  # new user

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if (old.full_name or "") != (instance.full_name or ""):
        # Import here to avoid import cycles
        from superadmin.models import LearnerRegistration
        from superadmin.views import generate_and_attach_certificate

        issued_regs = (
            LearnerRegistration.objects
            .select_related("course", "business", "learner")
            .filter(learner=instance, certificate_issued_at__isnull=False)
        )
        for r in issued_regs:
            if r.certificate_file:
                try:
                    r.certificate_file.delete(save=False)
                except Exception:
                    pass
            generate_and_attach_certificate(r)



class EmailSubscription(models.Model):
    email = models.EmailField(unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Email subscription"
        verbose_name_plural = "Email subscriptions"

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email