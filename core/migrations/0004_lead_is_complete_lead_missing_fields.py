# Generated by Django 5.1.7 on 2025-04-12 09:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_customuser_accept_contact_customuser_cgu_accepted'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='is_complete',
            field=models.BooleanField(default=True, help_text='Indicates if all required fields are present'),
        ),
        migrations.AddField(
            model_name='lead',
            name='missing_fields',
            field=models.JSONField(blank=True, default=list, help_text='List of missing required fields'),
        ),
    ]
