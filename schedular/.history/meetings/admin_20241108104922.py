from django.contrib import admin
from .models import MeetingType

# Register the MeetingType model with the admin site
@admin.register(MeetingType)
class MeetingTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'default_duration', 'color_code')
    search_fields = ('name',)
    list_filter = ('name',)
    ordering = ('name',)