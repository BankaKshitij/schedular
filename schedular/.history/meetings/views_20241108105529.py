from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from users.models import UserProfile
from .models import Availability, MeetingType
from .serializers import AvailabilitySerializer, MeetingTypeSerializer
from django.utils import timezone
from .permissions import IsSuperUser
from rest_framework.permissions import IsAuthenticated

from pytz import timezone as pytz_timezone
def get_user_timezone(user):
    try:
        return pytz_timezone(user.userprofile.default_timezone)
    except UserProfile.DoesNotExist:
        return pytz_timezone('UTC')
    
class MeetingTypeAdminAPIView(APIView):
    # Only superusers can create meeting types, but authenticated users can view them
    def post(self, request):
        self.permission_classes = [IsAuthenticated, IsSuperUser]
        self.check_permissions(request)
        
        serializer = MeetingTypeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        self.permission_classes = [IsAuthenticated]
        self.check_permissions(request)
        
        meeting_types = MeetingType.objects.all()
        serializer = MeetingTypeSerializer(meeting_types, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class AvailabilityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Retrieve availability slots for the logged-in user
        user = request.user
        availabilities = Availability.objects.filter(user=user, is_active=True)
        serializer = AvailabilitySerializer(availabilities, many=True)
        return Response(serializer.data)

    def post(self, request):
        # Expecting an array of availability slots in the request data
        availabilities_data = request.data.get('availabilities', [])
        if not availabilities_data:
            return Response({"detail": "No availability slots provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        errors = []
        created_slots = []

        for availability_data in availabilities_data:
            serializer = AvailabilitySerializer(data=availability_data)
            if serializer.is_valid():
                serializer.save(user=request.user)  # Associate each slot with the logged-in user
                created_slots.append(serializer.data)
            else:
                errors.append(serializer.errors)

        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({"created_slots": created_slots}, status=status.HTTP_201_CREATED)


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