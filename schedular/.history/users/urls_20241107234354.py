from django.urls import path
from .views import LoginAPIView, LogoutAPIView

urlpatterns = [
    path('login/', LoginAPIView.as_view(), name='login'),  # Custom login endpoint
    path('logout/', LogoutAPIView.as_view(), name='logout')
]