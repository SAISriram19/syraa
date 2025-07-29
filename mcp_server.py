"""
MCP server for the clinic AI receptionist system.
This module provides FastAPI endpoints for appointment management and other clinic operations.
"""

import os
from fastapi import FastAPI, HTTPException, Header
from supabase import create_client, Client
from pydantic import BaseModel, Field
from typing import List, Optional
import uvicorn
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import uuid
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import google.generativeai as genai
import os
import pytz
from utils import (
    format_time_for_db,
    validate_user_id,
    convert_to_ist,
    format_datetime_for_google_calendar,
    IST
)

# Load environment variables
load_dotenv()

# Configure the generative AI model for summarization
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Initialize FastAPI app
app = FastAPI()

# Initialize Supabase client
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Pydantic Models for data validation
class Appointment(BaseModel):
    patient_name: str
    appointment_reason: str
    appointment_date: str
    appointment_time: str
    assigned_doctor: str
    event_id: Optional[str] = None
    user_id: Optional[str] = None
    call_id: Optional[str] = None
    appointment_id: Optional[str] = None
    current_status: str = "scheduled"

class Doctor(BaseModel):
    name: str
    specialty: str
    services: List[str]
    calendarId: str
    working_hours: str

class UserSettings(BaseModel):
    user_id: str
    doctor_details: List[Doctor]
    calendar_auth: Optional[dict] = None
    agent_phone: Optional[str] = None

class CalendarAuth(BaseModel):
    token: str
    refresh_token: str
    token_uri: str
    client_id: str
    client_secret: str
    scopes: List[str]

class ScheduleAppointmentBody(BaseModel):
    patient_name: str
    assigned_doctor: str
    appointment_date: str
    appointment_time: str
    appointment_reason: str

class CheckAvailabilityBody(BaseModel):
    doctor_name: str
    appointment_date: str
    appointment_time: str

class RescheduleAppointmentBody(BaseModel):
    appointment_id: str
    new_date: str
    new_time: str

class CancelAppointmentBody(BaseModel):
    appointment_id: str

class GetDoctorDetailsBody(BaseModel):
    pass

class AddCallHistoryBody(BaseModel):
    caller_number: str
    called_number: str
    call_start: str
    call_end: str
    call_duration: str
    call_status: str
    appointment_status: str
    call_summary: str

class GetUserIdBody(BaseModel):
    agent_phone: str

class GetAppointmentDetailsBody(BaseModel):
    patient_name: str
    assigned_doctor: Optional[str] = None
    appointment_date: Optional[str] = None

class ListAppointmentsBody(BaseModel):
    patient_name: str

class SummarizeCallBody(BaseModel):
    transcript: str

class GetAvailableSlotsBody(BaseModel):
    doctor_name: str
    appointment_date: str


# Placeholder for database interaction functions
def db_fetch_user_settings(user_id: str) -> Optional[UserSettings]:
    """Fetches user settings from Supabase."""
    try:
        # Validate and standardize user_id format
        validated_user_id = validate_user_id(user_id)
        
        response = supabase.table("user_settings").select("*").eq("user_id", validated_user_id).single().execute()
        if response.data:
            return UserSettings(**response.data)
        return None
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
        return None
    except Exception as e:
        print(f"Error fetching user settings: {e}")
        return None

@app.post("/get_user_settings")
async def get_user_settings(body: GetDoctorDetailsBody, user_id: str = Header(..., alias="X-User-Id"), call_id: str = Header(..., alias="X-Call-Id")) -> Optional[dict]:
    """
    Fetches the entire user settings object for a given user_id.
    """
    try:
        # Validate and standardize user_id format
        validated_user_id = validate_user_id(user_id)
        
        user_settings = db_fetch_user_settings(validated_user_id)
        if user_settings:
            return {"result": user_settings.dict()}
        return None
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
        return None
    except Exception as e:
        print(f"Error fetching user settings via tool: {e}")
        return None

def db_schedule_appointment(appointment: Appointment, user_id: str, call_id: str) -> Optional[Appointment]:
    """Schedules an appointment in Supabase."""
    try:
        # Validate and standardize user_id format
        validated_user_id = validate_user_id(user_id)
        
        appointment_data = appointment.dict()
        appointment_data["user_id"] = validated_user_id
        appointment_data["call_id"] = call_id
        response = supabase.table("appointment_details").insert(appointment_data).execute()
        if response.data:
            return Appointment(**response.data[0])
        return None
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
        return None
    except Exception as e:
        print(f"Error scheduling appointment: {e}")
        return None

def format_time_for_speech(time_str: str) -> str:
    """
    Convert 24-hour time format to natural speech format.
    
    Examples:
    - "14:00:00" -> "2:00 PM"
    - "09:30:00" -> "9:30 AM"
    - "12:00:00" -> "12:00 PM"
    """
    try:
        # Parse the time string
        time_obj = datetime.strptime(time_str, "%H:%M:%S").time()
        
        # Convert to 12-hour format
        hour = time_obj.hour
        minute = time_obj.minute
        
        # Determine AM/PM
        if hour == 0:
            formatted_hour = 12
            period = "AM"
        elif hour < 12:
            formatted_hour = hour
            period = "AM"
        elif hour == 12:
            formatted_hour = 12
            period = "PM"
        else:
            formatted_hour = hour - 12
            period = "PM"
        
        # Format the time
        if minute == 0:
            return f"{formatted_hour}:00 {period}"
        else:
            return f"{formatted_hour}:{minute:02d} {period}"
            
    except Exception as e:
        print(f"Error formatting time for speech: {e}")
        return time_str

def parse_working_hours(working_hours_str: str, appointment_date: str) -> tuple:
    """
    Parse working hours string and return start/end times for the given date.
    
    Examples:
    - "Monday-Saturday: 9:00 AM - 6:00 PM"
    - "Monday-Friday: 10:00 AM - 5:00 PM, Saturday: 10:00 AM - 2:00 PM"
    - "Monday-Wednesday-Friday: 11:00 AM - 7:00 PM, Tuesday-Thursday: 2:00 PM - 8:00 PM"
    
    Returns: (start_time_str, end_time_str) or (None, None) if not working that day
    """
    try:
        date_obj = datetime.strptime(appointment_date, "%Y-%m-%d")
        day_of_week = date_obj.strftime("%A")
        
        # Split by comma to handle multiple day ranges
        day_ranges = working_hours_str.split(', ')
        
        for day_range in day_ranges:
            if ':' not in day_range:
                continue
                
            days_part, hours_part = day_range.split(':', 1)
            days_part = days_part.strip()
            hours_part = hours_part.strip()
            
            # Parse days (handle ranges like "Monday-Friday" or "Monday-Wednesday-Friday")
            if '-' in days_part and ' - ' not in days_part:  # Day range, not time range
                if days_part.count('-') == 1:  # Simple range like "Monday-Friday"
                    start_day, end_day = days_part.split('-')
                    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                    start_idx = days.index(start_day.strip())
                    end_idx = days.index(end_day.strip())
                    working_days = days[start_idx:end_idx + 1]
                else:  # Complex range like "Monday-Wednesday-Friday"
                    working_days = [day.strip() for day in days_part.split('-')]
            else:  # Single day
                working_days = [days_part.strip()]
            
            # Check if appointment day is in working days
            if day_of_week in working_days:
                # Parse time range (e.g., "9:00 AM - 6:00 PM")
                if ' - ' in hours_part:
                    start_time_str, end_time_str = hours_part.split(' - ')
                    return start_time_str.strip(), end_time_str.strip()
        
        return None, None  # Not working on this day
        
    except Exception as e:
        print(f"Error parsing working hours '{working_hours_str}': {e}")
        return None, None

def is_within_working_hours(doctor_name: str, appointment_date: str, appointment_time: str, user_id: str) -> bool:
    """Check if appointment time is within doctor's working hours."""
    try:
        user_settings = db_fetch_user_settings(user_id)
        if not user_settings:
            print(f"No user settings found for working hours check")
            return False
        
        doctor = next((d for d in user_settings.doctor_details if d.name == doctor_name), None)
        if not doctor:
            print(f"Doctor {doctor_name} not found for working hours check")
            return False
        
        working_hours_str = doctor.working_hours
        if not working_hours_str:
            print(f"No working hours defined for {doctor_name}")
            return False
        
        # Parse working hours for the appointment date
        start_time_str, end_time_str = parse_working_hours(working_hours_str, appointment_date)
        
        if not start_time_str or not end_time_str:
            print(f"Doctor {doctor_name} is not working on {appointment_date}")
            return False
        
        # Convert times to comparable format
        appointment_time_formatted = format_time_for_db(appointment_time)
        start_time_formatted = format_time_for_db(start_time_str)
        end_time_formatted = format_time_for_db(end_time_str)
        
        # Compare times
        appointment_dt = datetime.strptime(appointment_time_formatted, "%H:%M:%S").time()
        start_dt = datetime.strptime(start_time_formatted, "%H:%M:%S").time()
        end_dt = datetime.strptime(end_time_formatted, "%H:%M:%S").time()
        
        is_within = start_dt <= appointment_dt <= end_dt
        print(f"Working hours check for {doctor_name}: {start_time_str}-{end_time_str}, appointment: {appointment_time}, within hours: {is_within}")
        
        return is_within
        
    except Exception as e:
        print(f"Error checking working hours: {e}")
        return False

def db_check_availability(doctor_name: str, appointment_date: str, appointment_time: str) -> bool:
    """Checks doctor availability in Supabase."""
    try:
        # Format time consistently before checking
        formatted_time = format_time_for_db(appointment_time)
        response = supabase.table("appointment_details").select("*").eq("assigned_doctor", doctor_name).eq("appointment_date", appointment_date).eq("appointment_time", formatted_time).eq("current_status", "scheduled").execute()
        return not response.data
    except Exception as e:
        print(f"Error checking availability: {e}")
        return False

def db_reschedule_appointment(appointment_id: str, new_date: str, new_time: str) -> Optional[Appointment]:
    """Reschedules an appointment in Supabase."""
    try:
        # Format time consistently before updating
        formatted_time = format_time_for_db(new_time)
        response = supabase.table("appointment_details").update({
            "appointment_date": new_date, 
            "appointment_time": formatted_time
        }).eq("appointment_id", appointment_id).execute()
        if response.data:
            return Appointment(**response.data[0])
        return None
    except Exception as e:
        print(f"Error rescheduling appointment: {e}")
        return None

def db_cancel_appointment(appointment_id: str) -> Optional[Appointment]:
    """Cancels an appointment in Supabase."""
    try:
        response = supabase.table("appointment_details").update({"current_status": "cancelled"}).eq("appointment_id", appointment_id).execute()
        if response.data:
            return Appointment(**response.data[0])
        return None
    except Exception as e:
        print(f"Error cancelling appointment: {e}")
        return None

def db_get_clinic_prefix(user_id: str) -> Optional[str]:
    """Fetches the first 3 letters of the clinic name from the profiles table."""
    try:
        # Validate and standardize user_id format
        validated_user_id = validate_user_id(user_id)
        
        response = supabase.table("profiles").select("name").eq("id", validated_user_id).single().execute()
        if response.data and response.data.get("name"):
            return response.data["name"][:3].upper()
        return None
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
        return None
    except Exception as e:
        print(f"Error fetching clinic prefix: {e}")
        return None

def db_get_last_appointment_numeric_id(prefix: str) -> int:
    """Finds the last appointment number for a given clinic prefix."""
    try:
        response = supabase.table("appointment_details").select("appointment_id").like("appointment_id", f"{prefix}-%").execute()
        if not response.data:
            return 0
        
        max_id = 0
        for item in response.data:
            try:
                numeric_part = int(item['appointment_id'].split('-')[1])
                if numeric_part > max_id:
                    max_id = numeric_part
            except (IndexError, ValueError):
                pass # Continue if parsing fails
        return max_id
    except Exception as e:
        print(f"Error fetching last appointment ID: {e}")
        return 0

def db_update_call_history_status(call_id: str, status: str) -> None:
    """Updates the appointment_status in the call_history table."""
    try:
        supabase.table("call_history").update({"appointment_status": status}).eq("call_id", call_id).execute()
    except Exception as e:
        print(f"Error updating call history: {e}")

# MCP Tools
@app.post("/schedule_appointment")
async def schedule_appointment(body: ScheduleAppointmentBody, user_id: str = Header(..., alias="X-User-Id"), call_id: str = Header(..., alias="X-Call-Id")) -> dict:
    """
    Schedules an appointment for a patient with a doctor.
    """
    try:
        # Validate and standardize user_id format
        validated_user_id = validate_user_id(user_id)
        
        # Format time consistently before checking availability
        formatted_time = format_time_for_db(body.appointment_time)
        
        # First check if appointment is within working hours
        is_within_hours = is_within_working_hours(body.assigned_doctor, body.appointment_date, formatted_time, validated_user_id)
        print(f"DEBUG: Checking working hours for {body.assigned_doctor} on {body.appointment_date} at {formatted_time}: {is_within_hours}")
        
        if not is_within_hours:
            print(f"DEBUG: Appointment outside working hours, checking available slots...")
            # Get available slots within working hours
            slots_body = GetAvailableSlotsBody(doctor_name=body.assigned_doctor, appointment_date=body.appointment_date)
            available_slots_response = await get_available_slots(slots_body, user_id=validated_user_id, call_id=call_id)
            available_slots = available_slots_response.get("result", [])
            if available_slots:
                # Format times for natural speech
                formatted_slots = [format_time_for_speech(slot) for slot in available_slots]
                return {"result": f"Doctor {body.assigned_doctor} is not available at {format_time_for_speech(formatted_time)} on {body.appointment_date} (outside working hours). However, they have openings at: {', '.join(formatted_slots)}. Would any of these times work for you?"}
            else:
                return {"result": f"Doctor {body.assigned_doctor} is not working on {body.appointment_date}. Please choose a different date."}
        
        # Then check if slot is already booked
        is_available = db_check_availability(body.assigned_doctor, body.appointment_date, formatted_time)
        print(f"DEBUG: Checking slot availability for {body.assigned_doctor} on {body.appointment_date} at {formatted_time}: {is_available}")
        
        if not is_available:
            print(f"DEBUG: Slot not available, checking for alternative slots...")
            # Create a GetAvailableSlotsBody object to call get_available_slots
            slots_body = GetAvailableSlotsBody(doctor_name=body.assigned_doctor, appointment_date=body.appointment_date)
            available_slots_response = await get_available_slots(slots_body, user_id=validated_user_id, call_id=call_id)
            available_slots = available_slots_response.get("result", [])
            if available_slots:
                # Format times for natural speech
                formatted_slots = [format_time_for_speech(slot) for slot in available_slots]
                return {"result": f"Doctor {body.assigned_doctor} is not available at {format_time_for_speech(formatted_time)} on {body.appointment_date}. However, they have openings at: {', '.join(formatted_slots)}. Would any of these times work for you?"}
            else:
                return {"result": f"Doctor {body.assigned_doctor} is not available at {formatted_time} on {body.appointment_date}, and there are no other available slots on that day."}
        
        print(f"DEBUG: Slot is available, proceeding with appointment creation...")
        
        # Check for duplicate appointments with same call_id and patient details
        duplicate_check = supabase.table("appointment_details").select("*")\
            .eq("call_id", call_id)\
            .eq("patient_name", body.patient_name)\
            .eq("assigned_doctor", body.assigned_doctor)\
            .eq("appointment_date", body.appointment_date)\
            .eq("appointment_time", formatted_time)\
            .eq("current_status", "scheduled")\
            .execute()
        
        if duplicate_check.data:
            existing_appointment = duplicate_check.data[0]
            print(f"DEBUG: Found duplicate appointment: {existing_appointment['appointment_id']}")
            return {"result": "Appointment scheduled successfully."}

        clinic_prefix = db_get_clinic_prefix(validated_user_id)
        if not clinic_prefix:
            return {"result": "Failed to get clinic prefix for appointment ID generation."}

        last_numeric_id = db_get_last_appointment_numeric_id(clinic_prefix)
        new_numeric_id = last_numeric_id + 1
        new_appointment_id = f"{clinic_prefix}-{new_numeric_id:06d}"

        # Create appointment with formatted time
        appointment = Appointment(
            patient_name=body.patient_name,
            assigned_doctor=body.assigned_doctor,
            appointment_date=body.appointment_date,
            appointment_time=formatted_time,  # Use formatted time
            appointment_reason=body.appointment_reason,
            appointment_id=new_appointment_id,
            user_id=validated_user_id,
            call_id=call_id
        )

        print(f"DEBUG: Creating appointment in database...")
        new_appointment = db_schedule_appointment(appointment, validated_user_id, call_id)
        if not new_appointment:
            print(f"DEBUG: Failed to create appointment in database")
            return {"result": "Failed to schedule appointment."}

        print(f"DEBUG: Appointment created successfully: {new_appointment.appointment_id}")
        print(f"DEBUG: Adding appointment to Google Calendar...")
        add_to_google_calendar(new_appointment, validated_user_id)
        
        print(f"DEBUG: Appointment scheduling completed successfully")
        return {"result": "Appointment scheduled successfully."}
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
        return {"result": f"Failed to schedule appointment: Invalid user_id format"}
    except Exception as e:
        print(f"Error scheduling appointment: {e}")
        return {"result": f"Failed to schedule appointment: {e}"}

@app.post("/check_availability")
async def check_availability(body: CheckAvailabilityBody, user_id: str = Header(..., alias="X-User-Id"), call_id: str = Header(..., alias="X-Call-Id")) -> dict:
    """
    Checks the availability of a doctor at a specific time.
    """
    try:
        # Validate and standardize user_id format
        validated_user_id = validate_user_id(user_id)
        
        # Format time consistently before checking availability
        formatted_time = format_time_for_db(body.appointment_time)
        
        if db_check_availability(body.doctor_name, body.appointment_date, formatted_time):
            return {"result": f"Doctor {body.doctor_name} is available at {formatted_time} on {body.appointment_date}."}
        else:
            return {"result": f"Doctor {body.doctor_name} is not available at {formatted_time} on {body.appointment_date}."}
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
        return {"result": f"Failed to check availability: Invalid user_id format"}
    except Exception as e:
        print(f"Error checking availability: {e}")
        return {"result": f"Failed to check availability: {e}"}

@app.post("/reschedule_appointment")
async def reschedule_appointment(body: RescheduleAppointmentBody, user_id: str = Header(..., alias="X-User-Id"), call_id: str = Header(..., alias="X-Call-Id")) -> dict:
    """
    Reschedules an existing appointment.
    """
    try:
        # Validate and standardize user_id format
        validated_user_id = validate_user_id(user_id)
        
        # Format time consistently
        formatted_time = format_time_for_db(body.new_time)
        
        # 1. Fetch old appointment details to get event_id and calendar_id
        try:
            response = supabase.table("appointment_details").select("*").eq("appointment_id", body.appointment_id).single().execute()
            old_appointment_data = response.data
            if not old_appointment_data:
                return {"result": "Appointment not found for rescheduling."}
            old_appointment = Appointment(**old_appointment_data)
        except Exception as e:
            print(f"Error fetching old appointment for reschedule: {e}")
            return {"result": "Failed to fetch old appointment details."}

        # 2. Delete the old event from Google Calendar
        if old_appointment.event_id:
            remove_from_google_calendar(old_appointment, validated_user_id)

        # 3. Update the database record with new date/time (using formatted time)
        updated_appointment = db_reschedule_appointment(body.appointment_id, body.new_date, formatted_time)
        if not updated_appointment:
            return {"result": "Failed to update appointment in database."}

        # 4. Create a new event in Google Calendar and get the new event_id
        add_to_google_calendar(updated_appointment, validated_user_id)

        return {"result": "Appointment rescheduled successfully."}
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
        return {"result": f"Failed to reschedule appointment: Invalid user_id format"}
    except Exception as e:
        print(f"Error rescheduling appointment: {e}")
        return {"result": f"Failed to reschedule appointment: {e}"}

@app.post("/cancel_appointment")
async def cancel_appointment(body: CancelAppointmentBody, user_id: str = Header(..., alias="X-User-Id"), call_id: str = Header(..., alias="X-Call-Id")) -> dict:
    """
    Cancels an existing appointment.
    """
    try:
        # Validate and standardize user_id format
        validated_user_id = validate_user_id(user_id)
        
        cancelled_appointment = db_cancel_appointment(body.appointment_id)
        if not cancelled_appointment:
            return {"result": "Failed to cancel appointment."}

        remove_from_google_calendar(cancelled_appointment, validated_user_id)

        return {"result": "Appointment cancelled successfully."}
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
        return {"result": f"Failed to cancel appointment: Invalid user_id format"}
    except Exception as e:
        print(f"Error cancelling appointment: {e}")
        return {"result": f"Failed to cancel appointment: {e}"}

def get_calendar_service(calendar_auth: dict):
    """Creates a Google Calendar service using the provided auth credentials."""
    try:
        credentials = service_account.Credentials.from_service_account_info(
            calendar_auth,
            scopes=['https://www.googleapis.com/auth/calendar']
        )
        return build('calendar', 'v3', credentials=credentials)
    except Exception as e:
        print(f"Error creating calendar service: {e}")
        return None

def add_to_google_calendar(appointment: Appointment, user_id: str):
    """Adds an appointment to Google Calendar."""
    try:
        # Validate and standardize user_id format
        validated_user_id = validate_user_id(user_id)
        
        user_settings = db_fetch_user_settings(validated_user_id)
        if not user_settings or not user_settings.calendar_auth:
            print("User settings or calendar auth not found.")
            return

        doctor = next((d for d in user_settings.doctor_details if d.name == appointment.assigned_doctor), None)
        if not doctor:
            print(f"Doctor {appointment.assigned_doctor} not found.")
            return

        # Format time consistently before creating calendar event
        formatted_time = format_time_for_db(appointment.appointment_time)
        
        # Use the utility function to format datetime for Google Calendar
        start_datetime = format_datetime_for_google_calendar(
            None, 
            appointment.appointment_date, 
            formatted_time
        )
        
        # Calculate end time (1 hour after start)
        start_dt = datetime.strptime(f"{appointment.appointment_date} {formatted_time}", "%Y-%m-%d %H:%M:%S")
        end_dt = start_dt + timedelta(hours=1)
        end_datetime = format_datetime_for_google_calendar(IST.localize(end_dt))

        service = get_calendar_service(user_settings.calendar_auth)
        event = {
            'summary': f"Appointment with {appointment.patient_name}",
            'description': appointment.appointment_reason,
            'start': {
                'dateTime': start_datetime,
                'timeZone': 'Asia/Kolkata',
            },
            'end': {
                'dateTime': end_datetime,
                'timeZone': 'Asia/Kolkata',
            },
        }

        try:
            created_event = service.events().insert(calendarId=doctor.calendarId, body=event).execute()
            supabase.table("appointment_details").update({
                "event_id": created_event['id']
            }).eq("appointment_id", appointment.appointment_id).execute()
        except Exception as e:
            print(f"Error creating calendar event: {e}")
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
    except Exception as e:
        print(f"An unexpected error occurred in add_to_google_calendar: {e}")

def update_google_calendar(appointment: Appointment, user_id: str):
    """Updates an appointment on Google Calendar."""
    try:
        # Validate and standardize user_id format
        validated_user_id = validate_user_id(user_id)
        
        user_settings = db_fetch_user_settings(validated_user_id)
        if not user_settings or not user_settings.calendar_auth:
            return

        doctor = next((d for d in user_settings.doctor_details if d.name == appointment.assigned_doctor), None)
        if not doctor:
            print(f"Doctor {appointment.assigned_doctor} not found.")
            return

        # Format time consistently before updating calendar event
        formatted_time = format_time_for_db(appointment.appointment_time)
        
        # Use the utility function to format datetime for Google Calendar
        start_datetime = format_datetime_for_google_calendar(
            None, 
            appointment.appointment_date, 
            formatted_time
        )
        
        # Calculate end time (1 hour after start)
        start_dt = datetime.strptime(f"{appointment.appointment_date} {formatted_time}", "%Y-%m-%d %H:%M:%S")
        end_dt = start_dt + timedelta(hours=1)
        end_datetime = format_datetime_for_google_calendar(IST.localize(end_dt))

        service = get_calendar_service(user_settings.calendar_auth)
        event = {
            'start': {
                'dateTime': start_datetime,
                'timeZone': 'Asia/Kolkata',
            },
            'end': {
                'dateTime': end_datetime,
                'timeZone': 'Asia/Kolkata',
            },
        }

        try:
            service.events().patch(calendarId=doctor.calendarId, eventId=appointment.event_id, body=event).execute()
        except Exception as e:
            print(f"Error updating calendar event: {e}")
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
    except Exception as e:
        print(f"An unexpected error occurred in update_google_calendar: {e}")

def remove_from_google_calendar(appointment: Appointment, user_id: str):
    """Removes an appointment from Google Calendar."""
    try:
        # Validate and standardize user_id format
        validated_user_id = validate_user_id(user_id)
        
        user_settings = db_fetch_user_settings(validated_user_id)
        if not user_settings or not user_settings.calendar_auth:
            return

        doctor = next((d for d in user_settings.doctor_details if d.name == appointment.assigned_doctor), None)
        if not doctor:
            print(f"Doctor {appointment.assigned_doctor} not found.")
            return

        service = get_calendar_service(user_settings.calendar_auth)

        try:
            service.events().delete(calendarId=doctor.calendarId, eventId=appointment.event_id).execute()
        except Exception as e:
            print(f"Error deleting calendar event: {e}")
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
    except Exception as e:
        print(f"An unexpected error occurred in remove_from_google_calendar: {e}")

@app.post("/get_doctor_details_for_user")
async def get_doctor_details_for_user(body: GetDoctorDetailsBody, user_id: str = Header(..., alias="X-User-Id"), call_id: str = Header(..., alias="X-Call-Id")) -> dict:
    """
    Fetches the doctor details for a given user_id.
    """
    try:
        # Validate and standardize user_id format
        validated_user_id = validate_user_id(user_id)
        
        user_settings = db_fetch_user_settings(validated_user_id)
        if not user_settings:
            return {"result": []}
        return {"result": [d.dict() for d in user_settings.doctor_details]}
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
        return {"result": []}
    except Exception as e:
        print(f"Error fetching doctor details: {e}")
        return {"result": []}

@app.post("/add_call_history")
async def add_call_history(body: AddCallHistoryBody, user_id: str = Header(..., alias="X-User-Id"), call_id: str = Header(..., alias="X-Call-Id")) -> dict:
    """
    Adds a call history record to the database.
    """
    try:
        # Validate and standardize user_id format
        validated_user_id = validate_user_id(user_id)
        
        # Keep datetime strings as-is for call history (they're already in ISO format)
        # Don't use format_time_for_db for datetime fields, only for time fields
        formatted_call_start = body.call_start
        formatted_call_end = body.call_end
        
        print(f"DEBUG: Received call_start: {body.call_start}")
        print(f"DEBUG: Received call_end: {body.call_end}")
        print(f"DEBUG: Storing call_start: {formatted_call_start}")
        print(f"DEBUG: Storing call_end: {formatted_call_end}")
        
        supabase.table("call_history").insert({
            "caller_number": body.caller_number,
            "called_number": body.called_number,
            "call_start": formatted_call_start,
            "call_end": formatted_call_end,
            "call_duration": body.call_duration,
            "call_status": body.call_status,
            "appointment_status": body.appointment_status,
            "call_summary": body.call_summary,
            "call_id": call_id,
            "user_id": validated_user_id,
        }).execute()
        return {"result": "Call history added successfully."}
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
        return {"result": f"Failed to add call history: Invalid user_id format"}
    except Exception as e:
        print(f"Error adding call history: {e}")
        return {"result": f"Failed to add call history: {e}"}

@app.post("/get_user_id_by_agent_phone")
async def get_user_id_by_agent_phone(body: GetUserIdBody, call_id: str = Header(..., alias="X-Call-Id")) -> Optional[dict]:
    """
    Fetches the user_id associated with a given agent_phone from user_settings.
    """
    try:
        print(f"DEBUG: Looking for user_id with agent_phone: {body.agent_phone}")
        response = supabase.table("user_settings").select("user_id").eq("agent_phone", body.agent_phone).single().execute()
        print(f"DEBUG: Database response: {response.data}")
        
        if response.data:
            # Validate and standardize user_id format before returning
            validated_user_id = validate_user_id(response.data["user_id"])
            print(f"DEBUG: Returning validated user_id: {validated_user_id}")
            return {"result": validated_user_id}
        
        print(f"DEBUG: No user found for agent_phone: {body.agent_phone}")
        return {"result": None}
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
        return {"result": None}
    except Exception as e:
        print(f"Error fetching user_id by agent phone: {e}")
        return {"result": None}

@app.post("/get_appointment_details")
async def get_appointment_details(body: GetAppointmentDetailsBody, user_id: str = Header(..., alias="X-User-Id"), call_id: str = Header(..., alias="X-Call-Id")) -> dict:
    """
    Fetches appointment details based on patient name, doctor, and date.
    """
    try:
        # Validate and standardize user_id format
        validated_user_id = validate_user_id(user_id)
        
        query = supabase.table("appointment_details").select("*").eq("user_id", validated_user_id)
        if body.patient_name:
            query = query.eq("patient_name", body.patient_name)
        if body.assigned_doctor:
            query = query.eq("assigned_doctor", body.assigned_doctor)
        if body.appointment_date:
            query = query.eq("appointment_date", body.appointment_date)
        
        response = query.execute()
        if response.data:
            return {"result": [Appointment(**d).dict() for d in response.data]}
        return {"result": []}
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
        return {"result": []}
    except Exception as e:
        print(f"Error getting appointment details: {e}")
        return {"result": []}

@app.post("/list_appointments_for_patient")
async def list_appointments_for_patient(body: ListAppointmentsBody, user_id: str = Header(..., alias="X-User-Id"), call_id: str = Header(..., alias="X-Call-Id")) -> dict:
    """
    Lists all upcoming appointments for a given patient.
    """
    try:
        # Validate and standardize user_id format
        validated_user_id = validate_user_id(user_id)
        
        today = datetime.now().strftime("%Y-%m-%d")
        response = supabase.table("appointment_details").select("*")\
            .eq("user_id", validated_user_id)\
            .eq("patient_name", body.patient_name)\
            .gte("appointment_date", today)\
            .order("appointment_date", desc=False)\
            .order("appointment_time", desc=False)\
            .execute()
        if response.data:
            return {"result": [Appointment(**d).dict() for d in response.data]}
        return {"result": []}
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
        return {"result": []}
    except Exception as e:
        print(f"Error listing appointments for patient: {e}")
        return {"result": []}

@app.post("/summarize_call")
async def summarize_call(body: SummarizeCallBody) -> dict:
    """
    Summarizes a given conversation transcript using an LLM.
    """
    try:
        model = genai.GenerativeModel('gemini-pro') # Using gemini-pro for summarization
        response = model.generate_content(f"Summarize the following conversation transcript concisely, focusing on key actions like appointments scheduled, rescheduled, or cancelled, and any clinic information provided:\n\n{body.transcript}")
        return {"result": response.text}
    except Exception as e:
        print(f"Error summarizing call: {e}")
        return {"result": f"Failed to summarize call: {e}"}

@app.post("/get_available_slots")
async def get_available_slots(body: GetAvailableSlotsBody, user_id: str = Header(..., alias="X-User-Id"), call_id: str = Header(..., alias="X-Call-Id")) -> dict:
    """
    Fetches available 30-minute appointment slots for a given doctor on a specific date.
    """
    try:
        # Validate and standardize user_id format
        validated_user_id = validate_user_id(user_id)
        
        user_settings = db_fetch_user_settings(validated_user_id)
        if not user_settings:
            return {"result": []}

        doctor = next((d for d in user_settings.doctor_details if d.name == body.doctor_name), None)
        if not doctor:
            return {"result": []}

        # Get day of the week from appointment_date
        date_obj = datetime.strptime(body.appointment_date, "%Y-%m-%d")
        day_of_week = date_obj.strftime("%A")

        working_hours_str = doctor.working_hours
        if not working_hours_str:
            return {"result": []}

        # Use the new working hours parsing function
        start_time_str, end_time_str = parse_working_hours(working_hours_str, body.appointment_date)
        
        if not start_time_str or not end_time_str:
            # Doctor is not working on this day
            return {"result": []}
        
        # Format working hours consistently
        formatted_start_time = format_time_for_db(start_time_str)
        formatted_end_time = format_time_for_db(end_time_str)

        # Create datetime objects with formatted times
        start_dt = IST.localize(datetime.strptime(f"{body.appointment_date} {formatted_start_time}", "%Y-%m-%d %H:%M:%S"))
        end_dt = IST.localize(datetime.strptime(f"{body.appointment_date} {formatted_end_time}", "%Y-%m-%d %H:%M:%S"))

        # Fetch booked appointments
        response = supabase.table("appointment_details").select("appointment_time").eq("assigned_doctor", body.doctor_name).eq("appointment_date", body.appointment_date).eq("current_status", "scheduled").execute()
        
        # Extract booked times
        booked_times = [item["appointment_time"] for item in response.data]
        
        # Generate available slots (30-minute intervals) - limit to first 4 slots
        available_slots = []
        current_dt = start_dt
        max_slots = 4  # Limit to 4 slots maximum
        
        while current_dt < end_dt and len(available_slots) < max_slots:
            current_time_str = current_dt.strftime("%H:%M:%S")
            if current_time_str not in booked_times:
                available_slots.append(current_time_str)
            current_dt += timedelta(minutes=30)
        
        print(f"DEBUG: Returning {len(available_slots)} available slots (max {max_slots}): {available_slots}")
        return {"result": available_slots}
    except ValueError as e:
        print(f"Invalid user_id format: {e}")
        return {"result": []}
    except Exception as e:
        print(f"Error getting available slots: {e}")
        return {"result": []}

@app.get("/health")
async def health_check():
    """Health check endpoint for deployment monitoring"""
    return {
        "status": "healthy",
        "service": "SYRAA Clinic MCP Server",
        "timestamp": datetime.now(IST).isoformat()
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "SYRAA Clinic AI Receptionist MCP Server",
        "status": "running",
        "docs": "/docs"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)