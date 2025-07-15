import os
import pickle
from datetime import datetime, timezone
from lxml import etree
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'primary'
LOCAL_XML_PATH = 'Appointments.xml'

def get_google_calendar_service():
    creds = None
    if os.path.exists('token.pkl'):
        with open('token.pkl', 'rb') as token:
            creds = pickle.load(token)
    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.pkl', 'wb') as token:
            pickle.dump(creds, token)
    return build('calendar', 'v3', credentials=creds)

def unix_to_rfc3339(timestamp):
    dt = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    return dt.isoformat()

def parse_local_xml(path):
    tree = etree.parse(path)
    appointments = []
    for appointment in tree.findall('Appointment'):
        id = appointment.find('ID').text
        start = int(appointment.find('Start').text) // 10000000  # Convert nanoseconds to seconds
        end = int(appointment.find('End').text) // 10000000  # Convert nanoseconds to seconds
        description = appointment.find('Description').text
        reminder = appointment.find('Reminder').text == 'True'
        appointments.append({
            'id': id,
            'start': start,
            'end': end,
            'description': description,
            'reminder': reminder
        })
    return appointments

def get_google_events(service):
    now = datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=now,
        maxResults=250,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events_result.get('items', [])

def sync_xml_to_google(service, local_events, google_events):
    google_event_titles = {e['summary']: e for e in google_events}
    print(local_events)
    for local_event in local_events:
        title = local_event['description']
        if title not in google_event_titles:
            event_body = {
                'summary': local_event['description'],
                'start': {
                    'dateTime': local_event['start'],
                    'timeZone': 'Europe/Paris',
                },
                'end': {
                    'dateTime': local_event['end'],
                    'timeZone': 'Europe/Paris',
                },
                'description': f"Synced from local XML - ID {local_event['id']}"
            }
            created = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
            print(f"✅ Event created: {created['summary']} at {created['start']['dateTime']}")
        else:
            print(f"🔁 Event already exists: {title}")

def main():
    print("🚀 Starting calendar sync...")
    service = get_google_calendar_service()
    local_events = parse_local_xml(LOCAL_XML_PATH)
    google_events = get_google_events(service)
    sync_xml_to_google(service, local_events, google_events)
    print("✅ Sync complete.")

if __name__ == '__main__':
    main()