from django.urls import path
from .views import AvailabilityView, AvailabilityDetailView

urlpatterns = [
    path('api/availability', AvailabilityView.as_view(), name='availability-list'),
    path('api/availability/<int:id>', AvailabilityDetailView.as_view(), name='availability-detail'),
]