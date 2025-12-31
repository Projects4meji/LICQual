"""
Django management command to delete superuser(s)
Usage: 
  python manage.py delete_superuser --email user@example.com
  python manage.py delete_superuser --delete-all
"""
from django.core.management.base import BaseCommand, CommandError
from users.models import CustomUser


class Command(BaseCommand):
    help = 'Delete existing superuser(s)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email address of the superuser to delete'
        )
        parser.add_argument(
            '--delete-all',
            action='store_true',
            help='Delete all existing superusers'
        )

    def handle(self, *args, **options):
        email = options.get('email')
        delete_all = options.get('delete_all', False)

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('DELETE SUPERUSER'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # List existing superusers
        existing_superusers = CustomUser.objects.filter(is_superuser=True)
        if existing_superusers.exists():
            self.stdout.write(f"\nExisting superusers found: {existing_superusers.count()}")
            for user in existing_superusers:
                self.stdout.write(f"  - {user.email} ({user.full_name or 'no name'})")
        else:
            self.stdout.write(self.style.WARNING("\nNo superusers found."))
            return

        # Delete superusers
        if delete_all:
            deleted_count = existing_superusers.count()
            emails_deleted = [u.email for u in existing_superusers]
            existing_superusers.delete()
            self.stdout.write(self.style.WARNING(f"\nDeleted {deleted_count} superuser(s):"))
            for email in emails_deleted:
                self.stdout.write(f"  - {email}")
            self.stdout.write(self.style.SUCCESS("\nAll superusers deleted successfully!"))
        elif email:
            user_to_delete = CustomUser.objects.filter(email__iexact=email, is_superuser=True).first()
            if user_to_delete:
                user_email = user_to_delete.email
                user_to_delete.delete()
                self.stdout.write(self.style.WARNING(f"\nDeleted superuser: {user_email}"))
                self.stdout.write(self.style.SUCCESS("Superuser deleted successfully!"))
            else:
                raise CommandError(f"Superuser with email '{email}' not found.")
        else:
            raise CommandError("Please specify either --email or --delete-all option.")

