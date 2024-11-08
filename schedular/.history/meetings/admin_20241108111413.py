from django.contrib import admin
from .models import Availability, MeetingType

# Register the MeetingType model with the admin site
@admin.register(MeetingType)
class MeetingTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'default_duration', 'color_code')
    search_fields = ('name',)
    list_filter = ('name',)
    ordering = ('name',)

@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'meeting_type', 'day_of_week', 'start_time', 'end_time', 'is_active')
    list_filter = ('user', 'meeting_type', 'day_of_week', 'is_active')
    search_fields = ('user__email', 'meeting_type__name')