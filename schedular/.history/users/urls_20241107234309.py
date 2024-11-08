from django.urls import path
from .views import LoginAPIView, LogoutAPIView

urlpatterns = [
    path('api/login/', LoginAPIView.as_view(), name='login'),  # Custom login endpoint
    path('api/logout/', LogoutAPIView.as_view(), name='logout')
]