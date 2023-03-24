# Generated by Django 4.1.7 on 2023-03-07 22:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("codecov_auth", "0027_auto_20230307_1751"),
    ]

    operations = [
        migrations.AddField(
            model_name="owner",
            name="sentry_user_data",
            field=models.JSONField(null=True),
        ),
        migrations.AddField(
            model_name="owner",
            name="sentry_user_id",
            field=models.TextField(blank=True, null=True, unique=True),
        ),
    ]
