import json
from rest_framework.views import APIView
import pytz
from datetime import datetime
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from users.models import UserProfile
from .models import Availability, Meeting, MeetingAttendee, MeetingEditHistory, MeetingEditHistory, MeetingType
from .serializers import AvailabilitySerializer, MeetingTypeSerializer
from django.utils import timezone
from .permissions import IsSuperUser
from rest_framework.permissions import IsAuthenticated
from django.db import models
from django.db.models import Q
from openai import OpenAI


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
        # Get the authenticated user's profile to determine their timezone
        try:
            querying_user_profile = UserProfile.objects.get(user=request.user)
            querying_user_timezone = pytz.timezone(querying_user_profile.default_timezone)
        except UserProfile.DoesNotExist:
            return Response({"detail": "User profile not found for the querying user."}, status=status.HTTP_400_BAD_REQUEST)
        except pytz.UnknownTimeZoneError:
            return Response({"detail": "Invalid timezone in user profile."}, status=status.HTTP_400_BAD_REQUEST)

        user_id = request.query_params.get("user_id")

        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            user = request.user

        original_availabilities = Availability.objects.filter(user=user, is_active=True)

        # Fetch meetings where the user is either the organizer or an attendee
        if user == request.user:
            # User is viewing their own calendar
            meetings = Meeting.objects.filter(
                status__in=['scheduled', 'rescheduled', 'extended']
            ).filter(
                models.Q(organizer=user) | models.Q(meetingattendee__attendee=user)
            ).values("id", "title", "description", "start_time", "end_time", "organizer_id", "meetingattendee__attendee__username", "meetingattendee__attendee_id")

            # Also fetch focus time slots for the user
            focus_time_slots = Availability.objects.filter(user=user, meeting_type=1)

            # Serialize focus time slots
            focus_time_data = AvailabilitySerializer(focus_time_slots, many=True).data
        else:
            # User is viewing another user's calendar
            meetings = Meeting.objects.filter(
                organizer=user,
                status__in=['scheduled', 'rescheduled', 'extended']
            ).values("start_time", "end_time")
            focus_time_data = []  # No focus time data is shared if the user is viewing another user's calendar

        # Format the response for availability with timezone conversion
        original_data = []
        reference_date = datetime(2000, 1, 1)
        for availability in original_availabilities:
            start_dt_utc = datetime.combine(reference_date, availability.start_time)
            end_dt_utc = datetime.combine(reference_date, availability.end_time)
            start_dt_utc = pytz.utc.localize(start_dt_utc)
            end_dt_utc = pytz.utc.localize(end_dt_utc)
            start_dt_local = start_dt_utc.astimezone(querying_user_timezone)
            end_dt_local = end_dt_utc.astimezone(querying_user_timezone)

            original_data.append({
                "day_of_week": availability.day_of_week,
                "start_time": start_dt_local.strftime("%H:%M"),
                "end_time": end_dt_local.strftime("%H:%M"),
                "meeting_type": availability.meeting_type.id,
                "is_active": availability.is_active,
            })

        booked_slots = []
        if user == request.user:
            # Viewing their own calendar; provide more detailed information with attendee details
            for m in meetings:
                start_time_local = m["start_time"].astimezone(querying_user_timezone)
                end_time_local = m["end_time"].astimezone(querying_user_timezone)

                booked_slots.append({
                    "meeting_id": m["id"],
                    "title": m["title"],
                    "description": m["description"],
                    "start_time": start_time_local.strftime("%Y-%m-%dT%H:%M:%S"),
                    "end_time": end_time_local.strftime("%Y-%m-%dT%H:%M:%S"),
                    "attendee_id": m["meetingattendee__attendee_id"],
                    "attendee_username": m["meetingattendee__attendee__username"],
                })
        else:
            # Viewing another user's calendar; provide only the time slots
            for m in meetings:
                start_time_local = m["start_time"].astimezone(querying_user_timezone)
                end_time_local = m["end_time"].astimezone(querying_user_timezone)

                booked_slots.append({
                    "start_time": start_time_local.strftime("%Y-%m-%dT%H:%M:%S"),
                    "end_time": end_time_local.strftime("%Y-%m-%dT%H:%M:%S"),
                })

        # Convert focus time slots to querying user's timezone if needed
        if user == request.user:
            converted_focus_time_slots = []
            for focus_time in focus_time_slots:
                start_dt_utc = datetime.combine(reference_date, focus_time.start_time)
                end_dt_utc = datetime.combine(reference_date, focus_time.end_time)
                start_dt_utc = pytz.utc.localize(start_dt_utc)
                end_dt_utc = pytz.utc.localize(end_dt_utc)
                start_dt_local = start_dt_utc.astimezone(querying_user_timezone)
                end_dt_local = end_dt_utc.astimezone(querying_user_timezone)

                converted_focus_time_slots.append({
                    "day_of_week": focus_time.day_of_week,
                    "start_time": start_dt_local.strftime("%H:%M"),
                    "end_time": end_dt_local.strftime("%H:%M"),
                    "meeting_type": focus_time.meeting_type.id,
                    "is_active": focus_time.is_active,
                })
        else:
            converted_focus_time_slots = []

        # Create the response data
        response_data = {
            "original_availability": original_data,
            "booked_slots": booked_slots,
        }

        # Include focus time slots if the user is viewing their own calendar
        if user == request.user:
            response_data["focus_time_slots"] = converted_focus_time_slots

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
                
                if "start_time" in data:
                    start_naive = datetime.combine(reference_date, 
                                                 datetime.strptime(data["start_time"], "%H:%M").time())
                    start_local = user_profile_timezone.localize(start_naive)
                    start_utc = start_local.astimezone(pytz.UTC)
                    data["start_time"] = start_utc.time()

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
            availability = get_object_or_404(Availability, id=id, user=request.user)
            availability.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({"detail": f"An error occurred: {str(e)}"}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class ScheduleMeetingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
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

            start_time_organizer = start_time_utc.astimezone(organizer_timezone)
            end_time_organizer = end_time_utc.astimezone(organizer_timezone)

            day_of_week = start_time_organizer.weekday()

            # Convert start and end times back to UTC for availability checks
            start_time_for_query = start_time_utc.time()
            end_time_for_query = end_time_utc.time()

            # Check if the selected time is available in organizer's preferences and is not during focus time
            available_slots = Availability.objects.filter(
                user=organizer,
                day_of_week=day_of_week,
                start_time__lte=start_time_for_query,
                end_time__gte=end_time_for_query,
                is_active=True
            ).exclude(meeting_type=1)  # Exclude focus time slots

            if not available_slots.exists():
                return Response({"detail": "The selected time is not within the organizer's preferred availability."}, status=status.HTTP_400_BAD_REQUEST)

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
        meeting = get_object_or_404(Meeting, id=id)

        # The logged-in user must be the organizer
        if meeting.organizer != request.user:
            return Response({"detail": "You do not have permission to extend this meeting."}, status=status.HTTP_403_FORBIDDEN)

        # Get the new end_time and reason from the request data
        new_end_time_str = request.data.get("extended_end_time")
        extension_reason = request.data.get("reason", "")
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
                time_difference = new_end_time - meeting.end_time

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
                    # Save edit history before updating meeting details
                    MeetingEditHistory.objects.create(
                        meeting=meeting,
                        requested_by=request.user,
                        edit_type='extended',
                        original_times={
                            "start_time": meeting.start_time.isoformat(),
                            "end_time": meeting.end_time.isoformat()
                        },
                        new_times={
                            "start_time": meeting.start_time.isoformat(),
                            "end_time": new_end_time.isoformat()
                        },
                        reason=extension_reason
                    )

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
                with transaction.atomic():
                    MeetingEditHistory.objects.create(
                        meeting=meeting,
                        requested_by=request.user,
                        edit_type='extended',
                        original_times={
                            "start_time": meeting.start_time.isoformat(),
                            "end_time": meeting.end_time.isoformat()
                        },
                        new_times={
                            "start_time": meeting.start_time.isoformat(),
                            "end_time": new_end_time.isoformat()
                        },
                        reason=extension_reason
                    )

                    # Extend the current meeting
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

class UserDayMeetingsView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, date_str):
        # Get the authenticated user
        user = request.user

        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "Invalid date format. Please use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        # Get meetings where the user is either the organizer or an attendee on the given date
        meetings_as_organizer = Meeting.objects.filter(
            organizer=user,
            start_time__date=date,
            status__in=['scheduled', 'rescheduled']
        )

        meetings_as_attendee = Meeting.objects.filter(
            meetingattendee__attendee=user,
            start_time__date=date,
            status__in=['scheduled', 'rescheduled']
        ).exclude(organizer=user)

        meetings = meetings_as_organizer.union(meetings_as_attendee).order_by('start_time')

        meetings_data = []
        for meeting in meetings:
            attendees = MeetingAttendee.objects.filter(meeting=meeting)
            attendees_data = [
                {
                    "id": attendee.attendee.id,
                    "username": attendee.attendee.username,
                    "email": attendee.attendee.email
                }
                for attendee in attendees
            ]

            meetings_data.append({
                "id": meeting.id,
                "title": meeting.title,
                "description": meeting.description,
                "start_time": meeting.start_time,
                "end_time": meeting.end_time,
                "organizer": {
                    "id": meeting.organizer.id,
                    "username": meeting.organizer.username,
                    "email": meeting.organizer.email,
                },
                "attendees": attendees_data
            })

        return Response({"meetings": meetings_data}, status=status.HTTP_200_OK)

class RescheduleSuggestionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, meeting_id):
        try:
            meeting = Meeting.objects.get(id=meeting_id, organizer=request.user)
        except Meeting.DoesNotExist:
            return Response({"detail": "Meeting not found or you are not the organizer."}, status=status.HTTP_404_NOT_FOUND)

        # Get the attendees of the meeting
        attendees = MeetingAttendee.objects.filter(meeting=meeting).values_list('attendee', flat=True)

        # Retrieve availability of organizer and attendees
        all_availability = {}
        users_to_check = list(attendees) + [meeting.organizer.id]
        
        for user_id in users_to_check:
            user = User.objects.get(id=user_id)
            user_availabilities = Availability.objects.filter(user=user, is_active=True).exclude(meeting_type=1)  # Exclude focus times
            user_profile = UserProfile.objects.get(user=user)
            timezone = pytz.timezone(user_profile.default_timezone)

            availability_slots = []
            for avail in user_availabilities:
                availability_slots.append({
                    "day_of_week": avail.day_of_week,
                    "start_time": avail.start_time.strftime("%H:%M"),
                    "end_time": avail.end_time.strftime("%H:%M"),
                })

            # Retrieve existing meetings for the user to consider them as unavailable slots
            user_meetings = Meeting.objects.filter(
                models.Q(organizer=user) | models.Q(meetingattendee__attendee=user),
                status__in=['scheduled', 'rescheduled'],
                start_time__date=meeting.start_time.date()
            )
            blocked_slots = []
            for m in user_meetings:
                blocked_slots.append({
                    "start_time": m.start_time.astimezone(timezone).strftime("%H:%M"),
                    "end_time": m.end_time.astimezone(timezone).strftime("%H:%M"),
                })

            all_availability[user.username] = {
                "timezone": user_profile.default_timezone,
                "availability_slots": availability_slots,
                "blocked_slots": blocked_slots
            }

        # Format a prompt to request suggestions from GPT
        prompt = self.format_prompt(meeting, all_availability)
        suggestions = self.get_gpt_suggestions(prompt)

        if not suggestions:
            return Response({"detail": "Could not generate scheduling suggestions"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(suggestions, status=status.HTTP_200_OK)

    def format_prompt(self, meeting, all_availability):
        system_prompt = """You are an AI scheduling assistant. Your task is to analyze meeting participants' availability 
        and suggest optimal meeting times. For each suggestion, provide:
        1. The start and end times in ISO format (YYYY-MM-DDTHH:MM)
        2. A brief explanation of why this time works for all participants
        3. The API endpoint and payload needed to reschedule the meeting
        
        Format each suggestion as:
        Suggestion {number}:
        Start Time: {ISO datetime}
        End Time: {ISO datetime}
        Reasoning: {brief explanation}
        API Request:
        {curl command}"""

        user_prompt = f"""Please suggest rescheduling times for this meeting:
Meeting Title: {meeting.title}
Current Start Time: {meeting.start_time.strftime("%Y-%m-%d %H:%M")}
Current End Time: {meeting.end_time.strftime("%Y-%m-%d %H:%M")}
Duration: {(meeting.end_time - meeting.start_time).total_seconds() / 60} minutes
Organizer: {meeting.organizer.username}

Participant Availability:
"""

        for username, data in all_availability.items():
            user_prompt += f"\n{username} (Timezone: {data['timezone']})\n"
            user_prompt += "Available Slots:\n"
            for slot in data['availability_slots']:
                user_prompt += f"    Day: {slot['day_of_week']}, From: {slot['start_time']} to {slot['end_time']}\n"
            user_prompt += "Blocked Slots (existing meetings):\n"
            for slot in data['blocked_slots']:
                user_prompt += f"    From: {slot['start_time']} to {slot['end_time']}\n"

        return system_prompt, user_prompt

    def get_gpt_suggestions(self, prompt):
        client = OpenAI(api_key="sk-Ds9zatO9vLH7t335tYg3fef9pwMLROOLrajijGYTWrT3BlbkFJ-4-C8EyJzdoOIZHS3Xy6WOMTTDNkbW71oukGQYdLoA")
        system_prompt, user_prompt = prompt

        try:
            completion = client.chat.completions.create(
                model="gpt-4",  # You can adjust the model as needed
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )

            suggestions_text = completion.choices[0].message.content
            return self.parse_gpt_suggestions(suggestions_text)
        except Exception as e:
            print(f"Error generating suggestions: {str(e)}")
            return None

    def parse_gpt_suggestions(self, suggestions_text):
        suggestions = []
        current_suggestion = {}
        
        try:
            # Split text into individual suggestions
            suggestion_blocks = suggestions_text.split("Suggestion")[1:]  # Skip empty first split
            
            for block in suggestion_blocks:
                lines = block.strip().split('\n')
                current_suggestion = {}
                
                for line in lines:
                    line = line.strip()
                    if "Start Time:" in line:
                        current_suggestion['new_start_time'] = line.split("Start Time:")[1].strip()
                    elif "End Time:" in line:
                        current_suggestion['new_end_time'] = line.split("End Time:")[1].strip()
                    elif "Reasoning:" in line:
                        current_suggestion['reasoning'] = line.split("Reasoning:")[1].strip()
                    elif "curl" in line.lower():
                        current_suggestion['api_request'] = line.strip()

                if current_suggestion.get('new_start_time') and current_suggestion.get('new_end_time'):
                    suggestions.append(current_suggestion)

            return suggestions
        except Exception as e:
            print(f"Error parsing suggestions: {str(e)}")
            return None

        
class RescheduleMeetingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        meeting_id = request.data.get("meeting_id")
        new_start_time_str = request.data.get("new_start_time")
        new_end_time_str = request.data.get("new_end_time")
        reason = request.data.get("reason", "")

        if not all([meeting_id, new_start_time_str, new_end_time_str]):
            return Response({"detail": "Meeting ID, new start time, and new end time must be provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Get the meeting by ID
            meeting = get_object_or_404(Meeting, id=meeting_id, organizer=request.user)

            # Convert new start and end times to timezone-aware datetime
            user_profile = UserProfile.objects.get(user=meeting.organizer)
            user_timezone = pytz.timezone(user_profile.default_timezone)
            new_start_time = user_timezone.localize(datetime.strptime(new_start_time_str, "%Y-%m-%dT%H:%M"))
            new_end_time = user_timezone.localize(datetime.strptime(new_end_time_str, "%Y-%m-%dT%H:%M"))

            # Check if the new times conflict with existing meetings
            conflicting_meetings = Meeting.objects.filter(
                organizer=meeting.organizer,
                start_time__lt=new_end_time,
                end_time__gt=new_start_time,
                status__in=['scheduled', 'rescheduled']
            ).exclude(id=meeting.id)

            if conflicting_meetings.exists():
                return Response({"detail": "The new times conflict with another meeting."}, status=status.HTTP_400_BAD_REQUEST)

            # Reschedule the meeting transactionally
            with transaction.atomic():
                original_times = {
                    "start_time": meeting.start_time.isoformat(),
                    "end_time": meeting.end_time.isoformat()
                }
                new_times = {
                    "start_time": new_start_time.isoformat(),
                    "end_time": new_end_time.isoformat()
                }

                # Update the meeting with new times
                meeting.start_time = new_start_time
                meeting.end_time = new_end_time
                meeting.status = 'rescheduled'
                meeting.save()

                # Record the change in MeetingEditHistory
                MeetingEditHistory.objects.create(
                    meeting=meeting,
                    requested_by=request.user,
                    edit_type='rescheduled',
                    original_times=original_times,
                    new_times=new_times,
                    reason=reason
                )

            return Response({"detail": "Meeting rescheduled successfully"}, status=status.HTTP_200_OK)

        except UserProfile.DoesNotExist:
            return Response({"detail": "User profile not found for the organizer."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({"detail": "Invalid time format. Please use YYYY-MM-DDTHH:MM."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)