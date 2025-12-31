from django.db import migrations, connection

def drop_columns_if_exist(apps, schema_editor):
    """Drop columns if they exist, compatible with both PostgreSQL and SQLite"""
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE superadmin_business DROP COLUMN IF EXISTS timezone;")
            cursor.execute("ALTER TABLE superadmin_business DROP COLUMN IF EXISTS business_timezone;")
            cursor.execute("ALTER TABLE superadmin_business DROP COLUMN IF EXISTS next_invoice_issue_at;")
    # For SQLite, we skip this as columns likely don't exist in a fresh DB
    # and SQLite doesn't support DROP COLUMN IF EXISTS syntax

class Migration(migrations.Migration):
    dependencies = [
        ('superadmin', '0018_business_next_invoice_issue_at_business_timezone'),
    ]

    operations = [
        migrations.RunPython(drop_columns_if_exist, reverse_code=migrations.RunPython.noop),
    ]
