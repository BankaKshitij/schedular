from django.urls import path
from .views import LoginAPIView, AvailabilityView, AvailabilityDetailView, LogoutAPIView

urlpatterns = [
    path('api/login/', LoginAPIView.as_view(), name='login'),  # Custom login endpoint
    path('api/logout/', LogoutAPIView, name='logout')
]