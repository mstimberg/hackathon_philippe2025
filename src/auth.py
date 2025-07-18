import os
import pickle
from datetime import datetime, timezone, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import appdirs

# Configuration
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'primary'

def get_google_calendar_service():
    """Get authenticated Google Calendar service."""
    creds = None
    TOKEN_PATH = os.path.join(appdirs.user_data_dir("CalendarSync", roaming=True), 'token.pkl')
    print("token path: ", TOKEN_PATH)
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file(
            os.path.join(os.path.dirname(__file__), 'secrets', 'credentials.json'), 
            SCOPES
        )
        creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)
    return build('calendar', 'v3', credentials=creds)

def get_google_events(service, time_min=None, time_max=None):
    """
    Get Google Calendar events within a specified time range.
    
    Args:
        service: Google Calendar service object
        time_min: Minimum time for events (RFC3339 string), defaults to now
        time_max: Maximum time for events (RFC3339 string), optional
    """
    if time_min is None:
        time_min = datetime.now(timezone.utc).isoformat()
    
    params = {
        'calendarId': CALENDAR_ID,
        'timeMin': time_min,
        'maxResults': 250,
        'singleEvents': True,
        'orderBy': 'startTime'
    }
    
    if time_max:
        params['timeMax'] = time_max
    
    events_result = service.events().list(**params).execute()
    return events_result.get('items', [])

def get_events_past_week_to_next_month(service, fetch_days_past=7, fetch_days_future=30):
    """Get events from specified days ago to specified days from now."""
    now = datetime.now(timezone.utc)
    
    time_min = (now - timedelta(days=fetch_days_past)).isoformat()
    time_max = (now + timedelta(days=fetch_days_future)).isoformat()
        
    return get_google_events(service, time_min=time_min, time_max=time_max) 