from django.urls import path
from .views import AvailabilityView, AvailabilityDetailView, ExtendMeetingView, MeetingTypeAdminAPIView, RescheduleMeetingView, RescheduleSuggestionView, ScheduleMeetingView, UserDayMeetingsView

urlpatterns = [
    path('availability', AvailabilityView.as_view(), name='availability-list'),
    path('availability/<int:id>', AvailabilityDetailView.as_view(), name='availability-detail'),
    path('meeting-types', MeetingTypeAdminAPIView.as_view(), name='meeting-type-create'),
    path('schedule', ScheduleMeetingView.as_view(), name='schedule-meeting'),
    path('<uuid:id>/extend/', ExtendMeetingView.as_view(), name='extend-meeting'),
    path('day/<str:date_str>/', UserDayMeetingsView.as_view(), name='user_day_meetings'),
    path('reschedule/suggestions/<uuid:meeting_id>', RescheduleSuggestionView.as_view(), name='reschedule_suggestions'),
    path('reschedule/', RescheduleMeetingView.as_view(), name='reschedule_meeting'),

]