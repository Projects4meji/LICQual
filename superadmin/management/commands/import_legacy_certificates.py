import csv
import os
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.conf import settings
from superadmin.models import (
    LearnerRegistration, IsoIssuedCertificate, IsoCertification, 
    Business, Course
)
from users.models import CustomUser, Role
from django.utils import timezone


class Command(BaseCommand):
    help = 'Import legacy certificates from CSV files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--course-csv',
            type=str,
            help='Path to CSV file with course certificates (Learner Name, Certificate No, Course Title)'
        )
        parser.add_argument(
            '--iso-csv', 
            type=str,
            help='Path to CSV file with ISO certificates (Business, Scope, Address, Certificate No, IASCB Accreditation No, Management system, Issue Date, Expiry Date)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing'
        )
        parser.add_argument(
            '--default-business-id',
            type=int,
            help='Default business ID to use for course certificates (required if no email mapping)'
        )
        parser.add_argument(
            '--default-course-id', 
            type=int,
            help='Default course ID to use for course certificates (required if no course mapping)'
        )

    def handle(self, *args, **options):
        if not options['course_csv'] and not options['iso_csv']:
            raise CommandError('Please provide at least one CSV file (--course-csv or --iso-csv)')

        if options['course_csv']:
            self.import_course_certificates(
                options['course_csv'], 
                options['dry_run'],
                options.get('default_business_id'),
                options.get('default_course_id')
            )

        if options['iso_csv']:
            self.import_iso_certificates(options['iso_csv'], options['dry_run'])

    def import_course_certificates(self, csv_path, dry_run, default_business_id, default_course_id):
        """Import course certificates from CSV"""
        self.stdout.write(f"\n=== Importing Course Certificates from {csv_path} ===")
        
        if not os.path.exists(csv_path):
            raise CommandError(f"CSV file not found: {csv_path}")

        if not default_business_id or not default_course_id:
            raise CommandError(
                "For course certificates without emails, you must provide --default-business-id and --default-course-id"
            )

        try:
            business = Business.objects.get(id=default_business_id)
            course = Course.objects.get(id=default_course_id)
        except Business.DoesNotExist:
            raise CommandError(f"Business with ID {default_business_id} not found")
        except Course.DoesNotExist:
            raise CommandError(f"Course with ID {default_course_id} not found")

        # Get or create learner role
        learner_role, _ = Role.objects.get_or_create(name=Role.Names.LEARNER)

        imported_count = 0
        skipped_count = 0
        errors = []

        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 for header
                try:
                    learner_name = row.get('Learner Name', '').strip()
                    certificate_no = row.get('Certificate Number', '').strip()
                    course_title = row.get('Course Title', '').strip()
                    expiry_date_str = row.get('Expiry Date', '').strip()

                    if not learner_name or not certificate_no:
                        errors.append(f"Row {row_num}: Missing required fields")
                        continue

                    # Check if certificate already exists
                    if LearnerRegistration.objects.filter(certificate_number=certificate_no).exists():
                        self.stdout.write(f"Row {row_num}: Certificate {certificate_no} already exists, skipping")
                        skipped_count += 1
                        continue

                    # Parse expiry date if provided
                    expiry_date = None
                    if expiry_date_str:
                        try:
                            expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            try:
                                expiry_date = datetime.strptime(expiry_date_str, '%d/%m/%Y').date()
                            except ValueError:
                                try:
                                    expiry_date = datetime.strptime(expiry_date_str, '%d-%b-%y').date()
                                except ValueError:
                                    errors.append(f"Row {row_num}: Invalid expiry date format: {expiry_date_str}")
                                    continue

                    if dry_run:
                        expiry_info = f" (expires: {expiry_date})" if expiry_date else " (no expiry)"
                        self.stdout.write(f"Would import: {learner_name} - {certificate_no} - {course_title}{expiry_info}")
                        imported_count += 1
                        continue

                    with transaction.atomic():
                        # Create a placeholder user without email
                        # Use a unique identifier based on certificate number
                        placeholder_email = f"legacy_{certificate_no.lower()}@placeholder.local"
                        
                        # Check if user already exists
                        user = CustomUser.objects.filter(email__iexact=placeholder_email).first()
                        if not user:
                            user = CustomUser.objects.create_user(
                                email=placeholder_email,
                                password='legacy_import',  # Placeholder password
                                full_name=learner_name,
                                is_active=True,
                            )
                            # Add learner role
                            user.roles.add(learner_role)

                        # Create the registration
                        registration = LearnerRegistration.objects.create(
                            course=course,
                            business=business,
                            learner=user,
                            certificate_number=certificate_no,
                            certificate_issued_at=timezone.now(),
                            certificate_expiry_date=expiry_date,
                            status=LearnerRegistration.Status.ISSUED,
                            # Mark as legacy for identification
                            is_revoked=False,  # You might want to add a legacy flag
                        )

                        imported_count += 1
                        self.stdout.write(f"Imported: {learner_name} - {certificate_no}")

                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    continue

        self.stdout.write(f"\nCourse Certificates Summary:")
        self.stdout.write(f"  Imported: {imported_count}")
        self.stdout.write(f"  Skipped: {skipped_count}")
        if errors:
            self.stdout.write(f"  Errors: {len(errors)}")
            for error in errors[:10]:  # Show first 10 errors
                self.stdout.write(f"    {error}")

    def import_iso_certificates(self, csv_path, dry_run):
        """Import ISO certificates from CSV"""
        self.stdout.write(f"\n=== Importing ISO Certificates from {csv_path} ===")
        
        if not os.path.exists(csv_path):
            raise CommandError(f"CSV file not found: {csv_path}")

        imported_count = 0
        skipped_count = 0
        errors = []

        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row_num, row in enumerate(reader, start=2):
                try:
                    business_name = row.get('Company', '').strip()
                    scope = row.get('Scope', '').strip()
                    address = row.get('Address', '').strip()
                    certificate_no = row.get('Certificate No', '').strip()
                    iascb_no = row.get('IASCB Accreditation No', '').strip()  # May be empty
                    management_system = row.get('Management system', '').strip()
                    issue_date_str = row.get('Issue Date', '').strip()
                    expiry_date_str = row.get('Expiry Date', '').strip()

                    if not all([business_name, certificate_no, management_system]):
                        errors.append(f"Row {row_num}: Missing required fields")
                        continue

                    # Check if certificate already exists
                    if IsoIssuedCertificate.objects.filter(certificate_number=certificate_no).exists():
                        self.stdout.write(f"Row {row_num}: Certificate {certificate_no} already exists, skipping")
                        skipped_count += 1
                        continue

                    if dry_run:
                        self.stdout.write(f"Would import: {business_name} - {certificate_no} - {management_system}")
                        imported_count += 1
                        continue

                    with transaction.atomic():
                        # Parse dates
                        issue_date = None
                        expiry_date = None
                        
                        if issue_date_str:
                            try:
                                issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date()
                            except ValueError:
                                try:
                                    issue_date = datetime.strptime(issue_date_str, '%d/%m/%Y').date()
                                except ValueError:
                                    try:
                                        issue_date = datetime.strptime(issue_date_str, '%d-%b-%y').date()
                                    except ValueError:
                                        errors.append(f"Row {row_num}: Invalid issue date format: {issue_date_str}")
                                        continue

                        if expiry_date_str:
                            try:
                                expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
                            except ValueError:
                                try:
                                    expiry_date = datetime.strptime(expiry_date_str, '%d/%m/%Y').date()
                                except ValueError:
                                    try:
                                        expiry_date = datetime.strptime(expiry_date_str, '%d-%b-%y').date()
                                    except ValueError:
                                        errors.append(f"Row {row_num}: Invalid expiry date format: {expiry_date_str}")
                                        continue

                        # Get or create ISO certification
                        iso_cert, created = IsoCertification.objects.get_or_create(
                            standard=management_system,
                            defaults={
                                'management_system': management_system,
                                'iascb_accreditation_no': iascb_no if iascb_no else '',
                            }
                        )

                        # Get a default business for issuer (you might want to specify this)
                        issuer_business = Business.objects.first()
                        if not issuer_business:
                            raise CommandError("No business found to use as issuer. Please create a business first.")

                        # Create the ISO certificate
                        iso_certificate = IsoIssuedCertificate.objects.create(
                            iso=iso_cert,
                            issuer_business=issuer_business,
                            certified_business_name=business_name,
                            certified_business_address=address,
                            scope_text=scope,
                            certificate_number=certificate_no,
                            surveillance_1_date=issue_date or timezone.now().date(),
                            surveillance_2_date=expiry_date or timezone.now().date(),
                            expiry_date=expiry_date or timezone.now().date(),
                            recipient_email='',  # Empty for legacy certificates
                        )

                        imported_count += 1
                        self.stdout.write(f"Imported: {business_name} - {certificate_no}")

                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    continue

        self.stdout.write(f"\nISO Certificates Summary:")
        self.stdout.write(f"  Imported: {imported_count}")
        self.stdout.write(f"  Skipped: {skipped_count}")
        if errors:
            self.stdout.write(f"  Errors: {len(errors)}")
            for error in errors[:10]:
                self.stdout.write(f"    {error}")
