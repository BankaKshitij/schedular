from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from users.models import UserProfile
from .models import Availability
from .serializers import AvailabilitySerializer
from django.utils import timezone

from pytz import timezone as pytz_timezone
def get_user_timezone(user):
    try:
        return pytz_timezone(user.userprofile.default_timezone)
    except UserProfile.DoesNotExist:
        return pytz_timezone('UTC')

class AvailabilityView(APIView):
    def get(self, request):
        # Retrieve availability slots for the logged-in user
        user = request.user
        availabilities = Availability.objects.filter(user=user, is_active=True)
        serializer = AvailabilitySerializer(availabilities, many=True)
        return Response(serializer.data)

    def post(self, request):
        # Create a new availability slot for the logged-in user
        serializer = AvailabilitySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AvailabilityDetailView(APIView):
    def patch(self, request, id):
        # Update an existing availability slot
        availability = get_object_or_404(Availability, id=id, user=request.user)
        serializer = AvailabilitySerializer(availability, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, id):
        # Delete an existing availability slot
        availability = get_object_or_404(Availability, id=id, user=request.user)
        availability.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)