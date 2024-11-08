from rest_framework.views import APIView
import pytz
from datetime import datetime
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

        # Determine the timezone for the logged-in user
        user_timezone = request.user.userprofile.default_timezone if request.user.is_authenticated else 'UTC'
        tz = pytz.timezone(user_timezone)
        
        # Serialize the availability data with timezone conversion
        availability_data = []
        for availability in availabilities:
            # Combine the time with today's date and set it to UTC
            today = timezone.now().date()
            start_time_utc = timezone.make_aware(datetime.combine(today, availability.start_time), timezone=pytz.UTC)
            end_time_utc = timezone.make_aware(datetime.combine(today, availability.end_time), timezone=pytz.UTC)
            
            # Convert to user's timezone
            start_time_local = start_time_utc.astimezone(tz)
            end_time_local = end_time_utc.astimezone(tz)
            
            # Add converted times to the response data
            availability_data.append({
                "day_of_week": availability.day_of_week,
                "start_time": start_time_local.strftime("%H:%M"),
                "end_time": end_time_local.strftime("%H:%M"),
                "meeting_type": availability.meeting_type,
                "is_active": availability.is_active,
            })

        return Response(availability_data, status=status.HTTP_200_OK)

    def post(self, request):
        # Retrieve the authenticated user's timezone from UserProfile
        user = request.user
        try:
            user_profile = UserProfile.objects.get(user=user)
            user_timezone = pytz.timezone(user_profile.default_timezone)
        except UserProfile.DoesNotExist:
            return Response({"detail": "User profile not found"}, status=status.HTTP_400_BAD_REQUEST)
        except pytz.UnknownTimeZoneError:
            return Response({"detail": "Invalid timezone in user profile"}, status=status.HTTP_400_BAD_REQUEST)

        # Retrieve availabilities data from the request
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
                    slots = availability_data.get("slots")
                    
                    # Check if there are multiple slots for the day
                    if slots:
                        for slot in slots:
                            # Convert start and end times to UTC
                            try:
                                start_time_local = user_timezone.localize(datetime.strptime(slot.get("start_time"), "%H:%M"))
                                end_time_local = user_timezone.localize(datetime.strptime(slot.get("end_time"), "%H:%M"))
                                start_time_utc = start_time_local.astimezone(pytz.utc).time()
                                end_time_utc = end_time_local.astimezone(pytz.utc).time()
                            except ValueError:
                                errors.append({"day_of_week": day_of_week, "slot": slot, "errors": "Invalid time format"})
                                continue

                            slot_data = {
                                "day_of_week": day_of_week,
                                "start_time": start_time_utc,
                                "end_time": end_time_utc,
                                "meeting_type": slot.get("meeting_type"),
                                "is_active": slot.get("is_active", True)
                            }
                            serializer = AvailabilitySerializer(data=slot_data)
                            if serializer.is_valid():
                                serializer.save(user=user)
                                created_slots.append(serializer.data)
                            else:
                                errors.append({"day_of_week": day_of_week, "slot": slot, "errors": serializer.errors})
                    else:
                        # Process a single slot if `slots` is not specified
                        try:
                            start_time_local = user_timezone.localize(datetime.strptime(availability_data.get("start_time"), "%H:%M"))
                            end_time_local = user_timezone.localize(datetime.strptime(availability_data.get("end_time"), "%H:%M"))
                            availability_data["start_time"] = start_time_local.astimezone(pytz.utc).time()
                            availability_data["end_time"] = end_time_local.astimezone(pytz.utc).time()
                        except ValueError:
                            errors.append({"day_of_week": day_of_week, "errors": "Invalid time format"})
                            continue
                        
                        serializer = AvailabilitySerializer(data=availability_data)
                        if serializer.is_valid():
                            serializer.save(user=user)
                            created_slots.append(serializer.data)
                        else:
                            errors.append({"day_of_week": day_of_week, "errors": serializer.errors})

                if errors:
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