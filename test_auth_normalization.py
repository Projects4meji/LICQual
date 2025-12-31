"""
Test email normalization in authentication
"""
import os
import django
from django.conf import settings
from django.contrib.auth import authenticate
from users.models import CustomUser

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

print("=" * 60)
print("AUTHENTICATION NORMALIZATION TEST")
print("=" * 60)

# Get email and password from user
email_input = input("\nEnter the superuser email (exactly as you type it in the login form): ").strip()
password_input = input("Enter the password: ").strip()

print(f"\nEnvironment: {settings.ENV}")
print(f"DEBUG: {settings.DEBUG}")

# Show what normalize_email does
from django.contrib.auth.base_user import BaseUserManager
manager = CustomUserManager()
normalized_email = manager.normalize_email(email_input)
print(f"\nInput email: '{email_input}'")
print(f"Normalized email: '{normalized_email}'")
print(f"Are they different? {email_input != normalized_email}")

# Check what's actually in the database
print("\n" + "-" * 60)
print("Database lookup:")
try:
    db_user = CustomUser.objects.get(email__iexact=email_input)
    print(f"Found user with email: '{db_user.email}'")
    print(f"  - Email in DB matches input (case-insensitive): {db_user.email.lower() == email_input.lower()}")
    print(f"  - Email in DB matches normalized: {db_user.email.lower() == normalized_email.lower()}")
    print(f"  - is_superuser: {db_user.is_superuser}")
    print(f"  - is_staff: {db_user.is_staff}")
    print(f"  - is_active: {db_user.is_active}")
except CustomUser.DoesNotExist:
    print(f"No user found with email: '{email_input}'")
    # Try normalized
    try:
        db_user = CustomUser.objects.get(email__iexact=normalized_email)
        print(f"But found user with normalized email: '{db_user.email}'")
        print("  ⚠️  ISSUE: Email case mismatch!")
    except CustomUser.DoesNotExist:
        print(f"Also no user found with normalized email: '{normalized_email}'")

# Test authentication with raw input
print("\n" + "-" * 60)
print("Authentication test (with raw input):")
auth_user = authenticate(email=email_input, password=password_input)
if auth_user:
    print(f"✓ Authentication SUCCESS with raw input")
else:
    print(f"✗ Authentication FAILED with raw input")

# Test authentication with normalized email
print("\nAuthentication test (with normalized email):")
auth_user2 = authenticate(email=normalized_email, password=password_input)
if auth_user2:
    print(f"✓ Authentication SUCCESS with normalized email")
else:
    print(f"✗ Authentication FAILED with normalized email")

# Show how AuthenticationForm processes it
print("\n" + "-" * 60)
print("How EmailAuthenticationForm processes it:")
from users.forms import EmailAuthenticationForm
from django.test import RequestFactory

factory = RequestFactory()
request = factory.post('/login/', {
    'username': email_input,  # Form uses 'username' field name
    'password': password_input
})

# Create form and test
form = EmailAuthenticationForm(data={'username': email_input, 'password': password_input})
print(f"Form is_valid: {form.is_valid()}")
if form.is_valid():
    # Check what cleaned_data contains
    print(f"Form cleaned_data['username']: '{form.cleaned_data['username']}'")
    
    # AuthenticationForm's authenticate uses cleaned_data['username'] as 'username' parameter
    # But Django's authenticate() needs 'email' parameter when USERNAME_FIELD is 'email'
    # Let's check what LoginView actually does
    print("\nDjango's AuthenticationForm passes 'username' to authenticate(),")
    print("but since USERNAME_FIELD='email', Django should map it correctly.")
    print("However, there might be a mismatch if email case differs!")
    
    # Manually test what Django does
    from django.contrib.auth import authenticate
    test_user = authenticate(request=request, username=form.cleaned_data['username'], password=password_input)
    if test_user:
        print("✓ Authentication via form's cleaned_data WORKS")
    else:
        print("✗ Authentication via form's cleaned_data FAILED")
        print("  This is likely the issue!")
else:
    print("Form errors:", form.errors)

print("\n" + "=" * 60)

