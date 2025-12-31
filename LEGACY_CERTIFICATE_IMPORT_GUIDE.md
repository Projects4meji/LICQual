# Legacy Certificate Import Guide

This guide explains how to import previously issued certificates from your old website into the new system.

## Overview

The system supports two types of certificates:
1. **Course Certificates** (Learner Name, Certificate No, Course Title)
2. **ISO Management System Certificates** (Business, Scope, Address, Certificate No, etc.)

## Problem with Course Certificates

The current system requires email addresses for course registrations because it creates user accounts. For legacy certificates without emails, we use placeholder emails like `legacy_ABC123@placeholder.local`.

## Step-by-Step Import Process

### 1. Prepare Your CSV Files

First, format your CSV files to match the expected structure:

#### For Course Certificates:
```csv
Learner Name,Certificate No,Course Title
John Doe,ABC12345,ISO 9001 Lead Auditor
Jane Smith,DEF67890,ISO 45001 Internal Auditor
```

#### For ISO Certificates:
```csv
Business,Scope,Address,Certificate No,IASCB Accreditation No,Management system,Issue Date,Expiry Date
ABC Corp,Quality Management,123 Main St,ISO001,12345,ISO 9001:2015,2023-01-15,2026-01-15
XYZ Ltd,Environmental Management,456 Oak Ave,ISO002,12346,ISO 14001:2015,2023-02-20,2026-02-20
```

**Note:** You can use the `prepare_csv_import.py` script to help format your existing CSV files.

### 2. Get Required IDs

Before importing, you need to identify:
- A default Business ID (for course certificates)
- A default Course ID (for course certificates)

Find these by running:
```bash
python manage.py shell
```

Then in the shell:
```python
from superadmin.models import Business, Course

# List all businesses
for b in Business.objects.all():
    print(f"ID: {b.id}, Name: {b.name}, Email: {b.email}")

# List all courses  
for c in Course.objects.all():
    print(f"ID: {c.id}, Title: {c.title}")
```

### 3. Run the Import Command

#### For Course Certificates:
```bash
python manage.py import_legacy_certificates \
    --course-csv "path/to/course_certificates.csv" \
    --default-business-id 1 \
    --default-course-id 1
```

#### For ISO Certificates:
```bash
python manage.py import_legacy_certificates \
    --iso-csv "path/to/iso_certificates.csv"
```

#### For Both Types:
```bash
python manage.py import_legacy_certificates \
    --course-csv "path/to/course_certificates.csv" \
    --iso-csv "path/to/iso_certificates.csv" \
    --default-business-id 1 \
    --default-course-id 1
```

### 4. Test with Dry Run

Before actually importing, test with the `--dry-run` flag:
```bash
python manage.py import_legacy_certificates \
    --course-csv "path/to/course_certificates.csv" \
    --default-business-id 1 \
    --default-course-id 1 \
    --dry-run
```

## How Verification Works for Legacy Certificates

### Course Certificates
- Legacy certificates are imported with placeholder emails
- They can still be verified using the certificate number
- The verification page will show the learner name and certificate details
- No email is displayed (since it's a placeholder)

### ISO Certificates  
- These work exactly like new certificates
- All fields are preserved and displayed during verification
- No special handling needed

## Important Notes

1. **Certificate Numbers**: Must be unique. The import will skip duplicates.

2. **Date Formats**: The import supports these date formats:
   - `YYYY-MM-DD` (e.g., 2023-01-15)
   - `DD/MM/YYYY` (e.g., 15/01/2023)

3. **Email Handling**: For course certificates without emails:
   - Placeholder emails are created in format: `legacy_{certificate_no}@placeholder.local`
   - These users are marked as learners but cannot log in
   - Verification still works using certificate numbers

4. **Business Assignment**: All legacy course certificates are assigned to the default business you specify.

5. **Course Assignment**: All legacy course certificates are assigned to the default course you specify.

## Troubleshooting

### Common Issues:

1. **"Business with ID X not found"**
   - Check that the business ID exists using the shell command above

2. **"Course with ID X not found"**  
   - Check that the course ID exists using the shell command above

3. **"Invalid date format"**
   - Ensure dates are in supported formats (YYYY-MM-DD or DD/MM/YYYY)

4. **"Certificate already exists"**
   - The import skips duplicate certificate numbers
   - This is normal behavior

### Verification Issues:

If certificates don't verify after import:
1. Check that the certificate number matches exactly
2. Ensure the certificate was marked as "issued" during import
3. Check the verification page shows the correct certificate type

## After Import

1. **Test Verification**: Try verifying a few certificates using the verification page
2. **Check Data**: Review the imported data in the Django admin
3. **Update Templates**: If needed, update certificate templates to handle legacy certificates differently

## Security Considerations

- Placeholder emails are not real email addresses
- Legacy users cannot log in to the system
- Only certificate verification is available for legacy certificates
- Consider adding a "Legacy Certificate" flag to distinguish them from new certificates

## Support

If you encounter issues:
1. Check the import command output for error messages
2. Use `--dry-run` to test before importing
3. Verify your CSV format matches the expected structure
4. Check that required Business and Course IDs exist
