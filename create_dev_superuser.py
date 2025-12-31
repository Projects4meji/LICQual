#!/usr/bin/env python
"""
Create a superuser for dev environment
Usage: python manage.py shell < create_dev_superuser.py
Or set ENV=dev in your .env file first
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from users.models import CustomUser
from django.conf import settings

print("=" * 60)
print("CREATE DEV SUPERUSER")
print("=" * 60)
print(f"Current ENV: {settings.ENV}")
print(f"DEBUG: {settings.DEBUG}")
print()

# Check if superuser already exists
email = input("Enter superuser email: ").strip()
if not email:
    print("Email is required!")
    exit(1)

# Check if user exists
try:
    user = CustomUser.objects.get(email=email)
    print(f"\nUser '{email}' already exists!")
    response = input("Make this user a superuser? (y/n): ").strip().lower()
    if response == 'y':
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        password = input("Enter new password (leave blank to keep current): ").strip()
        if password:
            user.set_password(password)
            print(f"Password updated!")
        user.save()
        print(f"\n✓ User '{email}' is now a superuser!")
    else:
        print("Cancelled.")
except CustomUser.DoesNotExist:
    # Create new superuser
    full_name = input("Enter full name (optional): ").strip() or ""
    password = input("Enter password: ").strip()
    if not password:
        print("Password is required!")
        exit(1)
    
    user = CustomUser.objects.create_superuser(
        email=email,
        password=password,
        full_name=full_name
    )
    print(f"\n✓ Superuser '{email}' created successfully!")
    print(f"  You can now login with:")
    print(f"  Email: {email}")
    print(f"  Password: {password}")

