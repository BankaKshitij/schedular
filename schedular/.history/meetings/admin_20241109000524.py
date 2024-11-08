from django.contrib import admin
from .models import Availability, Meeting, MeetingAttendee, MeetingEditHistory, MeetingType

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

@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ('title', 'organizer', 'start_time', 'end_time', 'status', 'priority')
    search_fields = ('title', 'organizer__username', 'organizer__email')
    list_filter = ('status', 'priority', 'start_time')

# Register the MeetingAttendee model
@admin.register(MeetingAttendee)
class MeetingAttendeeAdmin(admin.ModelAdmin):
    list_display = ('attendee', 'meeting', 'response_status', 'response_time')
    search_fields = ('attendee__username', 'attendee__email', 'meeting__title')
    list_filter = ('response_status',)

@admin.register(MeetingEditHistory)
class MeetingEditHistoryAdmin(admin.ModelAdmin):
    list_display = ('meeting', 'requested_by', 'edit_type', 'created_at')
    search_fields = ('meeting__title', 'requested_by__username')
    list_filter = ('edit_type',)

    def original_times(self, obj):
        return f"Start: {obj.original_time.get('start_time', 'N/A')}, End: {obj.original_time.get('end_time', 'N/A')}"
    
    def edited_times(self, obj):
        return f"Start: {obj.edited_time.get('start_time', 'N/A')}, End: {obj.edited_time.get('end_time', 'N/A')}"

    readonly_fields = ('original_times', 'edited_times')

    fieldsets = (
        (None, {
            'fields': ('meeting', 'requested_by', 'edit_type', 'reason', 'created_at')
        }),
        ('Times', {
            'fields': ('original_times', 'edited_times'),
        }),
    )

@admin.action(description="Delete all availability data")
def delete_all_availability(modeladmin, request, queryset):
    # Deletes all records in the Availability model
    Availability.objects.all().delete()

