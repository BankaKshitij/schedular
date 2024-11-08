from django.urls import path
from .views import AvailabilityView, AvailabilityDetailView, ExtendMeetingView, MeetingTypeAdminAPIView, ScheduleMeetingView

urlpatterns = [
    path('availability', AvailabilityView.as_view(), name='availability-list'),
    path('availability/<int:id>', AvailabilityDetailView.as_view(), name='availability-detail'),
    path('meeting-types', MeetingTypeAdminAPIView.as_view(), name='meeting-type-create'),
    path('schedule', ScheduleMeetingView.as_view(), name='schedule-meeting'),
    path('<uuid:id>/extend/', ExtendMeetingView.as_view(), name='extend-meeting'),
]