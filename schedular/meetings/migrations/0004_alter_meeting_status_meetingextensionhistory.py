# Generated by Django 4.2 on 2024-11-08 16:17

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('meetings', '0003_alter_availability_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='meeting',
            name='status',
            field=models.CharField(choices=[('scheduled', 'Scheduled'), ('rescheduled', 'Rescheduled'), ('cancelled', 'Cancelled'), ('completed', 'Completed'), ('extended', 'Extended')], default='scheduled', max_length=20),
        ),
        migrations.CreateModel(
            name='MeetingExtensionHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('original_end_time', models.DateTimeField()),
                ('new_end_time', models.DateTimeField()),
                ('reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('meeting', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extensions', to='meetings.meeting')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
