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
from django.db import models
from django.db.models import Q

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

        if user_id:
            # If user_id is provided, try to get the corresponding user object
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            # If no user_id is provided, default to the logged-in user
            user = request.user

        # Retrieve active availability slots for the specified user
        original_availabilities = Availability.objects.filter(user=user, is_active=True)

        # Fetch meetings where the user is either the organizer or an attendee
        if user == request.user:
            # User is viewing their own calendar
            meetings = Meeting.objects.filter(
                status__in=['scheduled', 'rescheduled']
            ).filter(
                models.Q(organizer=user) | models.Q(meetingattendee__attendee=user)
            ).values("id", "title", "description", "start_time", "end_time", "organizer_id")

            # Also fetch focus time slots for the user
            focus_time_slots = Availability.objects.filter(user=user, meeting_type=1)

            # Serialize focus time slots
            focus_time_data = AvailabilitySerializer(focus_time_slots, many=True).data
        else:
            # User is viewing another user's calendar
            meetings = Meeting.objects.filter(
                organizer=user,
                status__in=['scheduled', 'rescheduled']
            ).values("start_time", "end_time")
            focus_time_data = []  # No focus time data is shared if the user is viewing another user's calendar

        # Format the response for availability
        original_data = AvailabilitySerializer(original_availabilities, many=True).data

        # Format the booked slots depending on whether the user is viewing their own calendar or not
        if user == request.user:
            # Viewing their own calendar; provide more detailed information
            booked_slots = [
                {
                    "meeting_id": m["id"],
                    "title": m["title"],
                    "description": m["description"],
                    "start_time": m["start_time"],
                    "end_time": m["end_time"],
                    "organizer_id": m["organizer_id"]
                }
                for m in meetings
            ]
        else:
            # Viewing another user's calendar; provide only the time slots
            booked_slots = [
                {
                    "start_time": m["start_time"],
                    "end_time": m["end_time"]
                }
                for m in meetings
            ]

        # Create the response data
        response_data = {
            "original_availability": original_data,
            "booked_slots": booked_slots,
        }

        # Include focus time slots if the user is viewing their own calendar
        if user == request.user:
            response_data["focus_time_slots"] = focus_time_data

        return Response(response_data, status=status.HTTP_200_OK)


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

                            # Adjust day_of_week if the date has changed during conversion
                            start_day_adjustment = (start_utc.date() - reference_date.date()).days
                            adjusted_day_of_week = (day_of_week + start_day_adjustment) % 7

                            # Handle potential negative adjustment for day_of_week
                            if adjusted_day_of_week < 0:
                                adjusted_day_of_week += 7

                            # Set is_active to False if meeting_type is 'focus time'
                            meeting_type = slot.get("meeting_type")
                            is_active = False if meeting_type == 1 else slot.get("is_active", True)

                            # Prepare the slot data with adjusted day_of_week
                            slot_data = {
                                "day_of_week": adjusted_day_of_week,
                                "start_time": start_utc.time(),
                                "end_time": end_utc.time(),
                                "meeting_type": meeting_type,
                                "is_active": is_active
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
            print(start_time_naive)
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

            # Check if the selected time is available in organizer's preferences and is not during focus time
            available_slots = Availability.objects.filter(
                user=organizer,
                day_of_week=day_of_week,
                start_time__lte=start_time_organizer.time(),
                end_time__gte=end_time_organizer.time(),
                is_active=True
            ).exclude(meeting_type='focus time')  # Exclude focus time slots

            if not available_slots.exists():
                return Response({"detail": "The selected time is not within the organizer's preferred availability."}, status=status.HTTP_400_BAD_REQUEST)

            # Check if there are conflicting meetings for the organizer
            conflicting_meetings = Meeting.objects.filter(
                organizer=organizer,
                start_time__lt=end_time_utc,
                end_time__gt=start_time_utc,
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

            return Response({"detail": "Meeting scheduled successfully", "meeting_id": meeting.id}, status=status.HTTP_201_CREATED)

        except User.DoesNotExist:
            return Response({"detail": "Organizer not found."}, status=status.HTTP_404_NOT_FOUND)
        except UserProfile.DoesNotExist:
            return Response({"detail": "User profile not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({"detail": "Invalid time format. Please use YYYY-MM-DDTHH:MM."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class ExtendMeetingView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        # Retrieve the meeting by ID
        meeting = get_object_or_404(Meeting, id=id)

        # The logged-in user must be the organizer
        if meeting.organizer != request.user:
            return Response({"detail": "You do not have permission to extend this meeting."}, status=status.HTTP_403_FORBIDDEN)

        # Get the new end_time from the request data
        new_end_time_str = request.data.get("extended_end_time")
        if not new_end_time_str:
            return Response({"detail": "The new end time must be provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Convert new end_time to timezone-aware datetime
            user_profile = UserProfile.objects.get(user=meeting.organizer)
            user_timezone = pytz.timezone(user_profile.default_timezone)
            new_end_time = user_timezone.localize(datetime.strptime(new_end_time_str, "%Y-%m-%dT%H:%M"))

            # Ensure the new end time is after the current end time
            if new_end_time <= meeting.end_time:
                return Response({"detail": "The new end time must be after the current end time."}, status=status.HTTP_400_BAD_REQUEST)

            # Check if there are any conflicting meetings for the organizer after the current meeting
            next_meeting = Meeting.objects.filter(
                organizer=meeting.organizer,
                start_time__gte=meeting.end_time,
                status__in=['scheduled', 'rescheduled']
            ).order_by('start_time').first()

            if next_meeting:
                # Calculate the time difference required to push the next meeting
                time_difference = new_end_time - meeting.end_time

                # Calculate the proposed new start and end times for the next meeting
                proposed_start_time = next_meeting.start_time + time_difference
                proposed_end_time = next_meeting.end_time + time_difference

                # Check if the proposed new times conflict with the availability of all attendees of the next meeting
                next_meeting_attendees = MeetingAttendee.objects.filter(meeting=next_meeting)
                for attendee in next_meeting_attendees:
                    attendee_profile = UserProfile.objects.get(user=attendee.attendee)
                    attendee_timezone = pytz.timezone(attendee_profile.default_timezone)
                    proposed_start_time_attendee = proposed_start_time.astimezone(attendee_timezone)
                    proposed_end_time_attendee = proposed_end_time.astimezone(attendee_timezone)

                    # Check for conflicts in the attendee's other meetings
                    conflicting_meetings = Meeting.objects.filter(
                        models.Q(organizer=attendee.attendee) | models.Q(meetingattendee__attendee=attendee.attendee),
                        start_time__lt=proposed_end_time_attendee,
                        end_time__gt=proposed_start_time_attendee,
                        status__in=['scheduled', 'rescheduled']
                    ).exclude(id=next_meeting.id)

                    if conflicting_meetings.exists():
                        return Response({"detail": "The next meeting cannot be pushed because of conflicts in attendee schedules."}, status=status.HTTP_400_BAD_REQUEST)

                # No conflicts found, extend the current meeting and push the next one
                with transaction.atomic():
                    # Extend the current meeting
                    meeting.extended_end_time = new_end_time
                    meeting.end_time = new_end_time
                    meeting.status = 'extended'
                    meeting.save()

                    # Update the next meeting's start and end times
                    next_meeting.start_time = proposed_start_time
                    next_meeting.end_time = proposed_end_time
                    next_meeting.status = 'rescheduled'
                    next_meeting.save()

            else:
                # No next meeting, just extend the current one
                meeting.extended_end_time = new_end_time
                meeting.end_time = new_end_time
                meeting.status = 'extended'
                meeting.save()

            return Response({"detail": "Meeting extended successfully"}, status=status.HTTP_200_OK)

        except UserProfile.DoesNotExist:
            return Response({"detail": "User profile not found for the organizer."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({"detail": "Invalid time format. Please use YYYY-MM-DDTHH:MM."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
