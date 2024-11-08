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
        user_id = request.query_params.get("user_id")
        
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            user = request.user

        availabilities = Availability.objects.filter(user=user, is_active=True)
        
        # Get user timezone
        user_timezone = request.user.userprofile.default_timezone if request.user.is_authenticated else 'UTC'
        target_tz = pytz.timezone(user_timezone)
        
        availability_data = []
        for availability in availabilities:
            # Create a reference date in UTC (the actual date doesn't matter)
            reference_date = datetime(2000, 1, 1)
            
            # Create UTC datetime objects
            start_dt_utc = datetime.combine(reference_date, availability.start_time)
            end_dt_utc = datetime.combine(reference_date, availability.end_time)
            
            # Make them timezone-aware as UTC
            start_dt_utc = pytz.utc.localize(start_dt_utc)
            end_dt_utc = pytz.utc.localize(end_dt_utc)
            
            # Convert to target timezone
            start_dt_local = start_dt_utc.astimezone(target_tz)
            end_dt_local = end_dt_utc.astimezone(target_tz)

            availability_data.append({
                "day_of_week": availability.day_of_week,
                "start_time": start_dt_local.strftime("%H:%M"),
                "end_time": end_dt_local.strftime("%H:%M"),
                "meeting_type": availability.meeting_type.id if availability.meeting_type else None,
                "is_active": availability.is_active,
            })

        return Response(availability_data, status=status.HTTP_200_OK)

    def post(self, request):
        user = request.user
        try:
            user_profile = UserProfile.objects.get(user=user)
            user_profile_timezone = pytz.timezone(user_profile.default_timezone)
        except UserProfile.DoesNotExist:
            return Response({"detail": "User profile not found"}, status=status.HTTP_400_BAD_REQUEST)
        except pytz.UnknownTimeZoneError:
            return Response({"detail": "Invalid timezone in user profile"}, status=status.HTTP_400_BAD_REQUEST)

        availabilities_data = request.data.get('availabilities', [])
        if not availabilities_data:
            return Response({"detail": "No availability slots provided"}, status=status.HTTP_400_BAD_REQUEST)

        errors = []
        created_slots = []

        try:
            with transaction.atomic():
                for availability_data in availabilities_data:
                    day_of_week = availability_data.get("day_of_week")
                    slots = availability_data.get("slots", [])
                    
                    # If no slots provided, treat the availability_data itself as a slot
                    if not slots:
                        slots = [availability_data]

                    for slot in slots:
                        try:
                            # Use a fixed reference date for consistent conversion
                            reference_date = datetime(2000, 1, 1)
                            
                            # Parse times and combine with reference date
                            start_naive = datetime.combine(reference_date, 
                                                        datetime.strptime(slot.get("start_time"), "%H:%M").time())
                            end_naive = datetime.combine(reference_date, 
                                                    datetime.strptime(slot.get("end_time"), "%H:%M").time())
                            
                            # Localize to user's timezone
                            start_local = user_profile_timezone.localize(start_naive)
                            end_local = user_profile_timezone.localize(end_naive)
                            
                            # Convert to UTC
                            start_utc = start_local.astimezone(pytz.UTC)
                            end_utc = end_local.astimezone(pytz.UTC)

                            slot_data = {
                                "day_of_week": day_of_week,
                                "start_time": start_utc.time(),
                                "end_time": end_utc.time(),
                                "meeting_type": slot.get("meeting_type"),
                                "is_active": slot.get("is_active", True)
                            }

                            serializer = AvailabilitySerializer(data=slot_data)
                            if serializer.is_valid():
                                serializer.save(user=user)
                                created_slots.append(serializer.data)
                            else:
                                errors.append({"day_of_week": day_of_week, "slot": slot, "errors": serializer.errors})
                        except ValueError as e:
                            errors.append({"day_of_week": day_of_week, "slot": slot, "errors": str(e)})
                            continue

                response_data = {"created_slots": created_slots}
                if errors:
                    response_data["errors"] = errors

                return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"detail": "An error occurred", "error": str(e)}, 
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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