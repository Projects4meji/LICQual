# users/admin.py
from django.contrib import admin
from .models import CustomUser, Role, PasswordResetToken, EmailSubscription

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "full_name")
    list_filter = ("is_active", "is_staff", "is_superuser", "roles")
    filter_horizontal = ("roles",)

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "created_at", "expires_at")
    search_fields = ("user__email", "token")
    autocomplete_fields = ("user",)


from django.contrib import admin
from .models import EmailSubscription

@admin.register(EmailSubscription)
class EmailSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("email", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("email",)