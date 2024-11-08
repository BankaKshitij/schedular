from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
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
        # Get the user ID from the query parameters
        user_id = request.query_params.get("user_id")
        
        # If user_id is provided, try to retrieve that user's availability
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Default to the logged-in user's availability
            user = request.user

        # Retrieve active availability slots for the specified user
        availabilities = Availability.objects.filter(user=user, is_active=True)
        serializer = AvailabilitySerializer(availabilities, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        # Expecting an array of availability slots in the request data
        availabilities_data = request.data.get('availabilities', [])
        if not availabilities_data:
            return Response({"detail": "No availability slots provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        errors = []
        created_slots = []

        try:
            with transaction.atomic():
                # Loop through each availability entry
                for availability_data in availabilities_data:
                    day_of_week = availability_data.get("day_of_week")
                    # Check if there are multiple slots for the day
                    slots = availability_data.get("slots")
                    if slots:
                        # If slots are specified, process each slot separately
                        for slot in slots:
                            slot_data = {
                                "day_of_week": day_of_week,
                                "start_time": slot.get("start_time"),
                                "end_time": slot.get("end_time"),
                                "meeting_type": slot.get("meeting_type"),
                                "is_active": slot.get("is_active", True)
                            }
                            serializer = AvailabilitySerializer(data=slot_data)
                            if serializer.is_valid():
                                serializer.save(user=request.user)
                                created_slots.append(serializer.data)
                            else:
                                errors.append({"day_of_week": day_of_week, "slot": slot, "errors": serializer.errors})
                    else:
                        # Process a single slot if `slots` is not specified
                        serializer = AvailabilitySerializer(data=availability_data)
                        if serializer.is_valid():
                            serializer.save(user=request.user)
                            created_slots.append(serializer.data)
                        else:
                            errors.append({"day_of_week": day_of_week, "errors": serializer.errors})

                if errors:
                    # If any errors are encountered, rollback all changes
                    raise ValueError("Validation errors occurred during creation")

        except ValueError:
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