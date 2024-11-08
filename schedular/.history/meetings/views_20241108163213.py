from rest_framework.views import APIView
import pytz
from datetime import datetime
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from users.models import UserProfile
from .models import Availability, Meeting, MeetingAttendee, MeetingType
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

                            # Adjust `day_of_week` if the date has changed during conversion
                            start_day_adjustment = (start_utc.date() - reference_date.date()).days
                            adjusted_day_of_week = (day_of_week + start_day_adjustment) % 7

                            # Handle potential negative adjustment for day_of_week
                            if adjusted_day_of_week < 0:
                                adjusted_day_of_week += 7

                            # Prepare the slot data with adjusted day_of_week
                            slot_data = {
                                "day_of_week": adjusted_day_of_week,
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
        try:
            # Get the availability and user's timezone
            availability = get_object_or_404(Availability, id=id, user=request.user)
            user_profile = UserProfile.objects.get(user=request.user)
            user_profile_timezone = pytz.timezone(user_profile.default_timezone)
        except UserProfile.DoesNotExist:
            return Response({"detail": "User profile not found"}, status=status.HTTP_400_BAD_REQUEST)
        except pytz.UnknownTimeZoneError:
            return Response({"detail": "Invalid timezone in user profile"}, status=status.HTTP_400_BAD_REQUEST)

        # Process the incoming times if they exist in the request
        data = request.data.copy()
        
        try:
            if "start_time" in data or "end_time" in data:
                reference_date = datetime(2000, 1, 1)
                
                # Handle start_time if provided
                if "start_time" in data:
                    start_naive = datetime.combine(reference_date, 
                                                 datetime.strptime(data["start_time"], "%H:%M").time())
                    start_local = user_profile_timezone.localize(start_naive)
                    start_utc = start_local.astimezone(pytz.UTC)
                    data["start_time"] = start_utc.time()

                # Handle end_time if provided
                if "end_time" in data:
                    end_naive = datetime.combine(reference_date, 
                                               datetime.strptime(data["end_time"], "%H:%M").time())
                    end_local = user_profile_timezone.localize(end_naive)
                    end_utc = end_local.astimezone(pytz.UTC)
                    data["end_time"] = end_utc.time()

            serializer = AvailabilitySerializer(availability, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
                
                # Convert the response times back to user's timezone for consistency
                response_data = serializer.data.copy()
                
                if "start_time" in response_data:
                    start_dt_utc = datetime.combine(reference_date, 
                                                  datetime.strptime(response_data["start_time"], "%H:%M:%S").time())
                    start_dt_utc = pytz.utc.localize(start_dt_utc)
                    start_dt_local = start_dt_utc.astimezone(user_profile_timezone)
                    response_data["start_time"] = start_dt_local.strftime("%H:%M")

                if "end_time" in response_data:
                    end_dt_utc = datetime.combine(reference_date, 
                                                datetime.strptime(response_data["end_time"], "%H:%M:%S").time())
                    end_dt_utc = pytz.utc.localize(end_dt_utc)
                    end_dt_local = end_dt_utc.astimezone(user_profile_timezone)
                    response_data["end_time"] = end_dt_local.strftime("%H:%M")

                return Response(response_data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except ValueError as e:
            return Response({"detail": f"Invalid time format: {str(e)}"}, 
                          status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": f"An error occurred: {str(e)}"}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, id):
        try:
            # Add user check to ensure users can only delete their own availabilities
            availability = get_object_or_404(Availability, id=id, user=request.user)
            availability.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({"detail": f"An error occurred: {str(e)}"}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class ScheduleMeetingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Get request data
        organizer_id = request.data.get("organizer_id")
        meeting_type_id = request.data.get("meeting_type")
        title = request.data.get("title")
        description = request.data.get("description", "")
        start_time_str = request.data.get("start_time")  # in "YYYY-MM-DDTHH:MM" format from the UI
        end_time_str = request.data.get("end_time")      # in "YYYY-MM-DDTHH:MM" format from the UI

        if not all([organizer_id, meeting_type_id, title, start_time_str, end_time_str]):
            return Response({"detail": "All required fields must be provided"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Get the organizer (person Y) and attendee (logged-in user, person X)
            organizer = User.objects.get(id=organizer_id)
            attendee = request.user

            # Get attendee's timezone (User X)
            attendee_profile = UserProfile.objects.get(user=attendee)
            attendee_timezone = pytz.timezone(attendee_profile.default_timezone)

            # Convert start and end times from attendee's timezone to UTC
            start_time_naive = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M")
            end_time_naive = datetime.strptime(end_time_str, "%Y-%m-%dT%H:%M")
            start_time_attendee = attendee_timezone.localize(start_time_naive)
            end_time_attendee = attendee_timezone.localize(end_time_naive)
            start_time_utc = start_time_attendee.astimezone(pytz.utc)
            end_time_utc = end_time_attendee.astimezone(pytz.utc)

            # Get organizer's timezone (User Y)
            organizer_profile = UserProfile.objects.get(user=organizer)
            organizer_timezone = pytz.timezone(organizer_profile.default_timezone)

            # Convert start and end times from UTC to organizer's timezone
            start_time_organizer = start_time_utc.astimezone(organizer_timezone)
            end_time_organizer = end_time_utc.astimezone(organizer_timezone)

            # Recalculate day of week in organizer's timezone
            day_of_week = start_time_organizer.weekday()

            # Check if the selected time is available in organizer's timezone
            available_slots = Availability.objects.filter(
                user=organizer,
                day_of_week=day_of_week,
                start_time__lte=start_time_organizer.time(),
                end_time__gte=end_time_organizer.time(),
                is_active=True
            )

            if not available_slots.exists():
                return Response({"detail": "The selected time is not available for the organizer."}, status=status.HTTP_400_BAD_REQUEST)

            # Check if there are conflicting meetings for the organizer
            conflicting_meetings = Meeting.objects.filter(
                organizer=organizer,
                start_time__lt=end_time_organizer,
                end_time__gt=start_time_organizer,
                status__in=['scheduled', 'rescheduled']
            )

            if conflicting_meetings.exists():
                return Response({"detail": "The selected time conflicts with another meeting."}, status=status.HTTP_400_BAD_REQUEST)

            # Schedule the meeting transactionally
            with transaction.atomic():
                # Create the meeting
                meeting = Meeting.objects.create(
                    organizer=organizer,
                    meeting_type_id=meeting_type_id,
                    title=title,
                    description=description,
                    start_time=start_time_utc,  # Store in UTC to be timezone agnostic
                    end_time=end_time_utc,      # Store in UTC to be timezone agnostic
                    status='scheduled'
                )

                # Add the attendee (logged-in user)
                MeetingAttendee.objects.create(
                    meeting=meeting,
                    attendee=attendee,
                    response_status='pending'
                )

                # Update availability - mark the slot as booked (not available)
                for slot in available_slots:
                    if slot.start_time <= start_time_organizer.time() and slot.end_time >= end_time_organizer.time():
                        slot.is_active = False
                        slot.save()

            return Response({"detail": "Meeting scheduled successfully", "meeting_id": meeting.id}, status=status.HTTP_201_CREATED)

        except User.DoesNotExist:
            return Response({"detail": "Organizer not found."}, status=status.HTTP_404_NOT_FOUND)
        except UserProfile.DoesNotExist:
            return Response({"detail": "User profile not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({"detail": "Invalid time format. Please use YYYY-MM-DDTHH:MM."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)