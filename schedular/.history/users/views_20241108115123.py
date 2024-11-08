# views.py
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from .models import UserProfile

class LoginSignupAPIView(APIView):
    permission_classes = [AllowAny]  # Allow access to unauthenticated users

    def post(self, request):
        username = request.data.get("username")
        email = request.data.get("email")
        password = request.data.get("password")
        default_timezone = request.data.get("default_timezone", "UTC")

        if not all([username, password]):
            return Response({"detail": "Username and password are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if the user already exists
        try:
            user = User.objects.get(username=username)
            
            # If user exists, attempt to authenticate
            user = authenticate(request, username=username, password=password)
            if user is not None:
                # Authentication successful, return token
                token, created = Token.objects.get_or_create(user=user)
                return Response({"token": token.key, "message": "User logged in successfully"}, status=status.HTTP_200_OK)
            else:
                # Authentication failed
                return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
            # User does not exist, so we create a new one
            try:
                with transaction.atomic():
                    # Create a new user and profile
                    user = User.objects.create_user(username=username, email=email, password=password)
                    UserProfile.objects.create(user=user, default_timezone=default_timezone)

                    # Generate token for the new user
                    token = Token.objects.create(user=user)
                    return Response({"token": token.key, "message": "User registered successfully"}, status=status.HTTP_201_CREATED)

            except Exception as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]  # Ensure only authenticated users can access this endpoint

    def post(self, request):
        # Check if the token exists in the request
        if request.auth:
            request.auth.delete()  # Delete the token to log the user out
            return Response({"message":"Logged out successfully"}, status=status.HTTP_204_NO_CONTENT)
        else:
            return Response({"error": "Token not provided"}, status=status.HTTP_400_BAD_REQUEST)


