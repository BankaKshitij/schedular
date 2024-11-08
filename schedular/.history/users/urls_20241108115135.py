from django.urls import path
from .views import LoginSignupAPIView, LogoutAPIView

urlpatterns = [
    path('login/', LoginSignupAPIView.as_view(), name='login'),  # Custom login endpoint
    path('logout/', LogoutAPIView.as_view(), name='logout')
]