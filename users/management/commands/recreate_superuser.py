"""
Django management command to delete and recreate superuser
Usage: python manage.py recreate_superuser --email user@example.com --password mypass --full-name "John Doe"
"""
from django.core.management.base import BaseCommand, CommandError
from users.models import CustomUser


class Command(BaseCommand):
    help = 'Delete existing superuser and create a new one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Email address for the new superuser'
        )
        parser.add_argument(
            '--password',
            type=str,
            required=True,
            help='Password for the new superuser'
        )
        parser.add_argument(
            '--full-name',
            type=str,
            default='',
            help='Full name for the new superuser (optional)'
        )
        parser.add_argument(
            '--delete-all',
            action='store_true',
            help='Delete all existing superusers (otherwise only deletes user with same email if exists)'
        )
        parser.add_argument(
            '--no-delete',
            action='store_true',
            help='Skip deletion, only create new superuser if email does not exist'
        )

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        full_name = options.get('full_name', '') or ''
        delete_all = options.get('delete_all', False)
        no_delete = options.get('no_delete', False)

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('SUPERUSER MANAGEMENT'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # List existing superusers
        existing_superusers = CustomUser.objects.filter(is_superuser=True)
        if existing_superusers.exists():
            self.stdout.write(f"\nExisting superusers found: {existing_superusers.count()}")
            for user in existing_superusers:
                self.stdout.write(f"  - {user.email} ({user.full_name or 'no name'})")
        else:
            self.stdout.write("\nNo existing superusers found.")

        # Delete superusers
        if not no_delete:
            if delete_all:
                deleted_count = existing_superusers.count()
                existing_superusers.delete()
                self.stdout.write(self.style.WARNING(f"\nDeleted {deleted_count} superuser(s)"))
            else:
                # Delete user with same email if exists (whether superuser or not)
                user_to_delete = CustomUser.objects.filter(email__iexact=email).first()
                if user_to_delete:
                    was_superuser = user_to_delete.is_superuser
                    user_to_delete.delete()
                    self.stdout.write(self.style.WARNING(f"\nDeleted existing user: {email} (was superuser: {was_superuser})"))
                else:
                    self.stdout.write(f"\nNo existing user with email '{email}' to delete")

        # Check if user already exists
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise CommandError(f"User with email '{email}' already exists. Use --delete-all or ensure email doesn't exist.")

        # Create new superuser
        self.stdout.write(f"\nCreating new superuser...")
        self.stdout.write(f"  Email: {email}")
        self.stdout.write(f"  Full Name: {full_name or '(not set)'}")
        
        try:
            CustomUser.objects.create_superuser(
                email=email,
                password=password,
                full_name=full_name
            )
            self.stdout.write(self.style.SUCCESS('\nSuperuser created successfully!'))
            self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
            self.stdout.write(self.style.SUCCESS('Login credentials:'))
            self.stdout.write(self.style.SUCCESS(f'  Email: {email}'))
            self.stdout.write(self.style.SUCCESS(f'  Password: {password}'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
        except Exception as e:
            raise CommandError(f"Error creating superuser: {e}")

