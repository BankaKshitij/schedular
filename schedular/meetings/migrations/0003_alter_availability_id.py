# Generated by Django 4.2 on 2024-11-08 05:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meetings', '0002_alter_availability_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='availability',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]