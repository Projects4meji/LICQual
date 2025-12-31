"""
Script to delete existing superuser and create a new one
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from users.models import CustomUser

print("=" * 60)
print("SUPERUSER MANAGEMENT")
print("=" * 60)

# List all superusers
superusers = CustomUser.objects.filter(is_superuser=True)
print(f"\nCurrent superusers found: {superusers.count()}")

if superusers.count() > 0:
    print("\nExisting superusers:")
    for idx, user in enumerate(superusers, 1):
        print(f"{idx}. Email: {user.email}")
        print(f"   Name: {user.full_name or '(not set)'}")
        print(f"   Active: {user.is_active}")
        print()
    
    # Ask which one to delete
    if superusers.count() == 1:
        user_to_delete = superusers.first()
        print(f"Only one superuser found: {user_to_delete.email}")
        confirm = input("Delete this superuser? (yes/no): ").strip().lower()
        if confirm == 'yes':
            email_to_delete = user_to_delete.email
        else:
            print("Cancelled.")
            exit(0)
    else:
        email_to_delete = input("\nEnter the email of the superuser to delete: ").strip()
        user_to_delete = CustomUser.objects.filter(email__iexact=email_to_delete, is_superuser=True).first()
        
        if not user_to_delete:
            print(f"Superuser with email '{email_to_delete}' not found.")
            exit(1)
    
    # Delete the superuser
    print(f"\nDeleting superuser: {user_to_delete.email}...")
    user_to_delete.delete()
    print("✓ Superuser deleted successfully!")
else:
    print("No existing superusers found.")

# Create new superuser
print("\n" + "=" * 60)
print("CREATE NEW SUPERUSER")
print("=" * 60)

email = input("\nEnter email address: ").strip()
if not email:
    print("Email is required.")
    exit(1)

full_name = input("Enter full name (optional): ").strip()
password = input("Enter password: ").strip()
if not password:
    print("Password is required.")
    exit(1)

password_confirm = input("Confirm password: ").strip()
if password != password_confirm:
    print("Passwords do not match.")
    exit(1)

# Check if user with this email already exists
existing_user = CustomUser.objects.filter(email__iexact=email).first()
if existing_user:
    print(f"\n⚠️  User with email '{email}' already exists!")
    overwrite = input("Delete existing user and create new superuser? (yes/no): ").strip().lower()
    if overwrite == 'yes':
        existing_user.delete()
        print("✓ Existing user deleted.")
    else:
        print("Cancelled.")
        exit(0)

# Create the superuser
print(f"\nCreating superuser with email: {email}...")
try:
    CustomUser.objects.create_superuser(
        email=email,
        password=password,
        full_name=full_name or ''
    )
    print("✓ Superuser created successfully!")
    print("\n" + "=" * 60)
    print("You can now log in with:")
    print(f"  Email: {email}")
    print(f"  Password: {password}")
    print("=" * 60)
except Exception as e:
    print(f"✗ Error creating superuser: {e}")
    exit(1)

