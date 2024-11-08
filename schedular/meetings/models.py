import uuid
from django.db import models
from django.contrib.auth.models import User

class MeetingType(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    default_duration = models.IntegerField(default=30)
    color_code = models.CharField(max_length=7, default="#000000")

    def __str__(self):
        return self.name

class Availability(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    meeting_type = models.ForeignKey(MeetingType, on_delete=models.CASCADE)
    day_of_week = models.IntegerField(choices=[
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
    ])
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['user', 'day_of_week', 'start_time', 'end_time']

    def __str__(self):
        return f"{self.user.email}'s availability on {self.get_day_of_week_display()}"

class Meeting(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('rescheduled', 'Rescheduled'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('extended', 'Extended')
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_meetings')
    meeting_type = models.ForeignKey(MeetingType, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    extended_end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

class MeetingAttendee(models.Model):
    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE)
    attendee = models.ForeignKey(User, on_delete=models.CASCADE)
    response_status = models.CharField(
        max_length=10, choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('declined', 'Declined')]
    )
    response_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.attendee.email} attending {self.meeting.title}"
    
class MeetingEditHistory(models.Model):
    """Tracks the history of meeting edits for analysis"""
    EDIT_TYPE_CHOICES = [
        ('extended', 'Extended'),
        ('rescheduled', 'Rescheduled'),
        ('canceled', 'Canceled')
    ]

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='edits')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE)
    edit_type = models.CharField(max_length=20, choices=EDIT_TYPE_CHOICES)
    original_times = models.JSONField()  # Example: {"start_time": "2024-11-12T09:00", "end_time": "2024-11-12T10:00"}
    new_times = models.JSONField(blank=True, null=True)  # Example: {"start_time": "2024-11-12T10:00", "end_time": "2024-11-12T11:00"}
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.edit_type.capitalize()} for {self.meeting.title} by {self.requested_by.username}"