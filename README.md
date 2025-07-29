# SYRAA Clinic Voice AI Receptionist

A sophisticated conversational AI agent designed to act as a virtual receptionist for medical clinics, handling patient calls, answering questions, and managing appointments.

## Overview

The SYRAA Clinic Voice AI Receptionist is an intelligent voice agent that automates front-desk operations for medical clinics. It integrates with Google Calendar for appointment management and uses a Supabase (PostgreSQL) database as its backend. The system provides a natural, human-like conversation experience for patients while efficiently handling administrative tasks.

## Key Features

### Conversational Appointment Management
- **Schedule Appointments**: Guide patients through booking new appointments
- **Check Availability**: Find available time slots based on doctor schedules
- **Reschedule Appointments**: Move existing appointments to new times
- **Cancel Appointments**: Remove appointments and update calendars

### Google Calendar Integration
- **Automatic Event Creation**: Create calendar events for each appointment
- **Event Updates & Deletion**: Sync calendar when appointments change
- **Per-Doctor Calendars**: Manage separate calendars for each doctor
- **Service Account Authentication**: Secure Google API integration

### Database Backend (Supabase)
- **Multi-tenant Architecture**: Support for multiple clinics
- **Appointment Tracking**: Complete record of all appointments
- **Call History**: Detailed logs of all patient interactions with call summaries
- **Clinic Configuration**: Customizable settings for each clinic

### Advanced Conversational AI
- **LiveKit Agents**: Framework for voice agent deployment
- **Google Gemini**: Powerful language model for natural conversations
- **Dynamic Prompt Engineering**: Real-time context updates
- **Tool-based Architecture**: Modular and extensible design

## System Architecture

The system consists of several key components:

1. **LiveKit Agent (`agent.py`, `tools.py`)**: Handles voice conversations and tool execution
2. **MCP Server (`mcp_server.py`)**: FastAPI server for business logic and database operations
3. **Supabase Database**: Persistent storage for clinic and appointment data
4. **Google Calendar API**: External service for scheduling
5. **Utility Layer (`utils.py`)**: Provides data consistency and validation

### Typical Flow (Scheduling an Appointment)

1. Patient calls the clinic's phone number
2. LiveKit receives the call and starts the agent
3. Agent fetches clinic configuration and doctor details
4. Agent converses with patient to collect appointment information
5. Agent calls the appropriate tool function (e.g., `schedule_appointment`)
6. Tool makes HTTP request to MCP server with proper authentication
7. Server validates data, checks availability, and updates database
8. Server creates Google Calendar event
9. Agent confirms booking with patient
10. Call history is recorded with appointment status and summary

## Data Consistency Features

The system implements several mechanisms to ensure data consistency:

1. **Standardized Time Formats**: All time values are converted to HH:MM:SS format
2. **User ID Validation**: UUIDs are validated and standardized across the system
3. **Timezone Handling**: All datetime operations use Indian Standard Time (IST)
4. **Parameter Validation**: Tool functions validate all parameters before use
5. **Error Recovery**: Graceful handling of errors with appropriate fallbacks

## Setup and Installation

### Prerequisites

- Python 3.11+
- PostgreSQL database (Supabase)
- Google Cloud account with Calendar API enabled
- LiveKit account for voice capabilities
- Docker (for deployment)

### Local Development

1. Clone the repository
2. Create a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Configure environment variables in `.env` file

### Configuration

1. Set up environment variables in `.env` file:
   - Google Calendar credentials
   - LiveKit credentials
   - Supabase URL and key
   - Other service credentials

2. Configure clinic settings in Supabase:
   - Add clinic details to `user_settings` table
   - Configure doctor information including specialties and working hours
   - Set up Google Calendar authentication

## Usage

### Starting the MCP Server

```
uvicorn mcp_server:app --reload
```

### Running the Agent

```
python agent.py dev
```

## Database Schema

The system uses the following key tables:

- **user_settings**: Clinic configuration and doctor details
- **appointment_details**: Appointment records
- **call_history**: Call interaction logs with appointment status and summaries
- **profiles**: Clinic profile information with clinic name for appointment ID generation

### Key Database Fields

#### appointment_details
- `appointment_id`: Unique identifier with clinic prefix (e.g., SYR-000001)
- `patient_name`: Name of the patient
- `assigned_doctor`: Doctor assigned to the appointment
- `appointment_date`: Date of the appointment
- `appointment_time`: Time of the appointment (HH:MM:SS)
- `appointment_reason`: Reason for the appointment
- `user_id`: Clinic's user ID
- `call_id`: ID of the call that created the appointment
- `current_status`: Status of the appointment (scheduled, cancelled)

#### call_history
- `call_id`: Unique identifier for the call
- `caller_number`: Phone number of the caller
- `called_number`: Phone number that was called
- `call_start`: Start time of the call
- `call_end`: End time of the call
- `call_duration`: Duration of the call
- `call_status`: Status of the call (completed, missed)
- `appointment_status`: Status of any appointment made (Booked, Rescheduled, Cancelled)
- `call_summary`: Summary of the call conversation

## Development

### Project Structure

- `agent.py`: Main agent implementation with LiveKit integration
- `tools.py`: Tool functions for agent capabilities with MCP server communication
- `utils.py`: Utility functions for data handling and consistency
- `mcp_server.py`: FastAPI server for business logic and database operations
- `test_utils.py`: Unit tests for utility functions

### Key Components

#### Agent (agent.py)
- Handles voice conversations using LiveKit
- Manages tool execution and context
- Tracks appointment status and call information
- Generates call summaries

#### Tools (tools.py)
- Provides functions for appointment management
- Ensures consistent parameter handling
- Communicates with MCP server via HTTP

#### MCP Server (mcp_server.py)
- Exposes API endpoints for appointment operations
- Handles database interactions
- Manages Google Calendar integration
- Validates and processes data

#### Utilities (utils.py)
- Ensures time format consistency
- Validates user IDs
- Handles timezone conversions
- Formats data for Google Calendar

### Testing

Run unit tests:

```
python -m unittest discover
```

## Troubleshooting

### Common Issues and Solutions

#### Database Validation Errors

**Issue**: Pydantic validation errors for missing `calendarId` and `working_hours` fields
```
doctor_details.0.calendarId Field required
doctor_details.0.working_hours Field required
```

**Solution**: Run the database setup script to fix doctor details:
```bash
python setup_database.py
```

Or manually update the database using the provided SQL script:
```bash
# Execute the SQL commands in fix_database_issues.sql
```

#### Invalid User ID Format

**Issue**: "Invalid user_id format" errors in logs

**Solution**: Ensure your `user_settings` table has proper UUID format for `user_id`:
1. Check current user_id format in database
2. Update to proper UUID format if needed
3. Ensure `profiles` table has matching entry

#### Calendar Integration Issues

**Issue**: "User settings or calendar auth not found" error

**Solutions**:
- Verify Google Calendar credentials are properly stored in `user_settings.calendar_auth`
- Check that the `calendarId` in doctor details matches your Google Calendar
- Ensure Google Calendar API is enabled in your Google Cloud project

#### Database Connection Errors

**Solutions**:
- Check Supabase URL and API key in `.env` file
- Verify network connectivity to Supabase
- Ensure database tables exist and have correct schema

#### Voice Agent Not Responding

**Solutions**:
- Verify LiveKit configuration and connectivity
- Check that all required environment variables are set
- Ensure MCP server is running on correct port (8000)

### Quick Database Setup

If you're setting up the system for the first time:

1. Run the database setup script:
   ```bash
   python setup_database.py
   ```

2. Verify the setup by checking the logs when starting the MCP server:
   ```bash
   uvicorn mcp_server:app --reload
   ```

3. Look for successful validation without Pydantic errors

### Debugging Tips

- Enable debug logging by setting environment variables
- Check MCP server logs for detailed error messages
- Use the provided SQL scripts to inspect database state
- Test individual components (database, calendar, voice) separately
- **Appointment ID Generation Fails**: Ensure clinic name is set in profiles table
- **Incorrect User ID Handling**: Check that user_id is properly set in agent context

## Recent Improvements

- **Enhanced Data Consistency**: Standardized time formats and user ID handling
- **Improved Error Handling**: Better recovery from API and database errors
- **Call Summary Generation**: Automatic summarization of call conversations
- **Appointment Status Tracking**: Proper tracking of appointment status (Booked, Rescheduled, Cancelled)
- **Parameter Validation**: Robust validation of all parameters before use

## License

[Specify license information]

## Contact

[Contact information for support or inquiries]