from django.contrib import admin
from .models import UserProfile, UserPersona

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'default_timezone')
    search_fields = ('user__email',)

@admin.register(UserPersona)
class UserPersonaAdmin(admin.ModelAdmin):
    list_display = ('user', 'avg_meeting_extension_time', 'extension_frequency', 'meetings_per_week', 'created_at', 'updated_at')
    search_fields = ('user__email',)
    readonly_fields = ('created_at', 'updated_at')