#!/usr/bin/env python
"""
Diagnostic script to check superuser status on dev vs production
Run: python manage.py shell < check_superuser.py
Or: python check_superuser.py (if you set DJANGO_SETTINGS_MODULE)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from users.models import CustomUser
from django.conf import settings

print("=" * 60)
print("SUPERUSER DIAGNOSTIC")
print("=" * 60)
print(f"Environment: {settings.ENV}")
print(f"DEBUG: {settings.DEBUG}")
print(f"SECRET_KEY first 20 chars: {settings.SECRET_KEY[:20]}...")
print()

# Check all superusers
superusers = CustomUser.objects.filter(is_superuser=True)
print(f"Total superusers found: {superusers.count()}")
print()

for user in superusers:
    print(f"Email: {user.email}")
    print(f"  - is_superuser: {user.is_superuser}")
    print(f"  - is_staff: {user.is_staff}")
    print(f"  - is_active: {user.is_active}")
    print(f"  - Has usable password: {user.has_usable_password()}")
    print()

# Check specific email if provided
import sys
if len(sys.argv) > 1:
    email = sys.argv[1]
    try:
        user = CustomUser.objects.get(email=email)
        print(f"\nUser '{email}' details:")
        print(f"  - Exists: Yes")
        print(f"  - is_superuser: {user.is_superuser}")
        print(f"  - is_staff: {user.is_staff}")
        print(f"  - is_active: {user.is_active}")
        print(f"  - Has usable password: {user.has_usable_password()}")
    except CustomUser.DoesNotExist:
        print(f"\nUser '{email}' does NOT exist in database")

