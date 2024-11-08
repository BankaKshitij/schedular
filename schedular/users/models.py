from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    default_timezone = models.CharField(max_length=50, default='UTC')

    def __str__(self):
        return f"{self.user.email}'s Profile"
