from django.urls import path
from .views import LoginAPIView, AvailabilityView, AvailabilityDetailView, LogoutAPIView

urlpatterns = [
    path('api/login/', LoginAPIView.as_view(), name='login'),  # Custom login endpoint
    path('api/logout/', LogoutAPIView, name='logout'),
    path('api/availability', AvailabilityView.as_view(), name='availability-list'),
    path('api/availability/<int:id>', AvailabilityDetailView.as_view(), name='availability-detail'),
]