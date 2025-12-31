from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ("superadmin", "0017_learnerregistration_is_revoked"),  # <-- use your actual 0017 filename
    ]

    # DB already has the columns, we just need this file to exist so the graph is valid.
    operations = []
