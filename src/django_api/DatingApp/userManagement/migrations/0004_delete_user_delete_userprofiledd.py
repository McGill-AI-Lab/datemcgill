# Generated by Django 5.1.4 on 2025-01-05 13:43

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('userManagement', '0003_rename_userprofile_userprofiledd'),
    ]

    operations = [
        migrations.DeleteModel(
            name='User',
        ),
        migrations.DeleteModel(
            name='UserProfileDD',
        ),
    ]
