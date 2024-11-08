from rest_framework import serializers
from .models import Meeting, MeetingType, Availability, MeetingAttendee

class MeetingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meeting
        fields = '__all__'

class MeetingTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingType
        fields = '__all__'

class AvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Availability
        fields = ['id', 'user', 'meeting_type', 'day_of_week', 'start_time', 'end_time', 'is_active']
        read_only_fields = ['user']  # user will be automatically set in views

class MeetingAttendeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingAttendee
        fields = '__all__'