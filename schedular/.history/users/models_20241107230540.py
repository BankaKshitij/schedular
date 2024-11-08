from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    default_timezone = models.CharField(max_length=50, default='UTC')

    def __str__(self):
        return f"{self.user.email}'s Profile"

class UserPersona(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avg_meeting_extension_time = models.IntegerField(default=0)
    extension_frequency = models.FloatField(default=0.0)
    meetings_per_week = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Persona for {self.user.email}"
