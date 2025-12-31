#!/usr/bin/env python
"""
Diagnose why superuser login works on prod but not dev
Run: python manage.py shell < diagnose_login_issue.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from users.models import CustomUser
from django.conf import settings
from django.contrib.auth import authenticate
import sys

print("=" * 70)
print("LOGIN ISSUE DIAGNOSTIC")
print("=" * 70)
print(f"ENV: {settings.ENV}")
print(f"DEBUG: {settings.DEBUG}")
print(f"Database: {settings.DATABASES['default']['NAME']}")
print(f"Database Host: {settings.DATABASES['default']['HOST']}")
print(f"SECRET_KEY set: {bool(settings.SECRET_KEY)}")
print(f"SECRET_KEY first 20: {settings.SECRET_KEY[:20] if settings.SECRET_KEY else 'N/A'}...")
print()

# Get email from command line or prompt
if len(sys.argv) > 1:
    email = sys.argv[1]
else:
    email = input("Enter superuser email to check: ").strip()

if not email:
    print("Email required!")
    sys.exit(1)

print(f"Checking user: {email}")
print("-" * 70)

# Check if user exists (case-insensitive)
try:
    # Try exact match first
    user = CustomUser.objects.get(email=email)
    print("✓ User found (exact email match)")
except CustomUser.DoesNotExist:
    # Try case-insensitive
    user = CustomUser.objects.filter(email__iexact=email).first()
    if user:
        print(f"⚠ User found but email case differs:")
        print(f"  Searched for: {email}")
        print(f"  Found: {user.email}")
    else:
        print(f"✗ User with email '{email}' NOT FOUND in database")
        print("\nPossible causes:")
        print("1. Dev and prod use DIFFERENT databases")
        print("2. User only exists in production database")
        print("3. Email spelling/case mismatch")
        sys.exit(1)

print(f"\nUser Details:")
print(f"  Email: {user.email}")
print(f"  is_superuser: {user.is_superuser}")
print(f"  is_staff: {user.is_staff}")
print(f"  is_active: {user.is_active}")
print(f"  Has usable password: {user.has_usable_password()}")
print()

# Test authentication
if len(sys.argv) > 2:
    password = sys.argv[2]
else:
    password = input("Enter password to test (or press Enter to skip): ").strip()

if password:
    print("\nTesting authentication...")
    authenticated_user = authenticate(email=email, password=password)
    
    if authenticated_user:
        print("✓ Authentication SUCCESSFUL")
        print(f"  Authenticated user: {authenticated_user.email}")
        print(f"  is_superuser: {authenticated_user.is_superuser}")
        print(f"  is_staff: {authenticated_user.is_staff}")
        print(f"  is_active: {authenticated_user.is_active}")
    else:
        print("✗ Authentication FAILED")
        print("\nPossible causes:")
        print("1. Wrong password")
        print("2. Password hash doesn't match (different SECRET_KEY when password was set)")
        print("3. User.is_active = False")
        print("4. Database connection issue")
        
        # Check if email normalization is the issue
        normalized_email = CustomUser.objects.normalize_email(email)
        if normalized_email != email:
            print(f"\n⚠ Email normalization difference:")
            print(f"  Original: {email}")
            print(f"  Normalized: {normalized_email}")
            
            try:
                norm_user = CustomUser.objects.get(email=normalized_email)
                print(f"  User with normalized email exists: {norm_user.email}")
            except CustomUser.DoesNotExist:
                print(f"  No user with normalized email found")
else:
    print("\nSkipping password test")

print("=" * 70)

