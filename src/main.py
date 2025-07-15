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

def dotnet_ticks_to_rfc3339(ticks):
    # .NET ticks are 100-nanosecond intervals since January 1, 0001 UTC
    # Unix epoch is January 1, 1970 UTC
    # There are 621355968000000000 ticks between 0001 and 1970
    unix_timestamp = (int(ticks) - 621355968000000000) / 10000000
    dt = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
    return dt.isoformat()

def rfc3339_to_dotnet_ticks(rfc3339_str):
    # Parse the RFC3339 datetime string
    dt = datetime.fromisoformat(rfc3339_str.replace('Z', '+00:00'))
    # Convert to UTC if not already
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    # Convert to Unix timestamp
    unix_timestamp = dt.timestamp()
    # Convert to .NET ticks (add offset and multiply by 10^7)
    dotnet_ticks = int((unix_timestamp * 10000000) + 621355968000000000)
    return str(dotnet_ticks)

def parse_local_xml(path):
    tree = etree.parse(path)
    root = tree.getroot()
    appointments = []
    for appointment in root.findall('Appointment'):
        id = appointment.find('ID').text
        start_ticks = appointment.find('Start').text
        end_ticks = appointment.find('End').text
        description = appointment.find('Description').text
        reminder = appointment.find('Reminder').text == 'True'
        appointments.append({
            'id': id,
            'start': dotnet_ticks_to_rfc3339(start_ticks),
            'end': dotnet_ticks_to_rfc3339(end_ticks),
            'description': description,
            'reminder': reminder
        })
    return appointments

def get_google_events(service):
    now = datetime.now(timezone.utc).isoformat()
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=now,
        maxResults=250,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events_result.get('items', [])

def sync_xml_to_google(service, local_events, google_events):
    google_event_titles = {e.get('summary', ''): e for e in google_events}
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

def sync_google_to_xml(google_events, local_events, xml_path):
    # Create a set of existing local event descriptions for comparison
    local_descriptions = {event['description'].strip() for event in local_events}
    
    # Find the highest existing ID to generate new ones
    existing_ids = [int(event['id']) for event in local_events if event['id'].isdigit()]
    next_id = max(existing_ids) + 1 if existing_ids else 1
    
    new_appointments = []
    
    for google_event in google_events:
        summary = google_event.get('summary', '').strip()
        description = google_event.get('description', '')
        
        # Skip events that were synced from local XML (to avoid duplicates)
        if "Synced from local XML" in description:
            continue
            
        # Skip if this event already exists in local XML
        if summary in local_descriptions:
            print(f"🔁 Event already exists in XML: {summary}")
            continue
        
        # Extract start and end times
        start_time = google_event.get('start', {})
        end_time = google_event.get('end', {})
        
        # Handle both dateTime and date fields
        start_datetime = start_time.get('dateTime') or start_time.get('date')
        end_datetime = end_time.get('dateTime') or end_time.get('date')
        
        if not start_datetime or not end_datetime:
            print(f"⚠️ Skipping event with missing date/time: {summary}")
            continue
        
        # Convert to .NET ticks
        start_ticks = rfc3339_to_dotnet_ticks(start_datetime)
        end_ticks = rfc3339_to_dotnet_ticks(end_datetime)
        
        new_appointments.append({
            'id': str(next_id),
            'start_ticks': start_ticks,
            'end_ticks': end_ticks,
            'description': summary,
            'reminder': False  # Default to False for Google events
        })
        
        print(f"📅 New appointment from Google: {summary}")
        next_id += 1
    
    if new_appointments:
        # Update the XML file
        write_appointments_to_xml(local_events + new_appointments, xml_path)
        print(f"✅ Added {len(new_appointments)} new appointments to XML")
    else:
        print("ℹ️ No new appointments to add to XML")

def write_appointments_to_xml(appointments, xml_path):
    # Create the root element
    root = etree.Element("AppointmentList")
    
    for appointment in appointments:
        # Create appointment element
        appt_elem = etree.SubElement(root, "Appointment")
        
        # Add child elements
        id_elem = etree.SubElement(appt_elem, "ID")
        id_elem.text = appointment['id']
        
        start_elem = etree.SubElement(appt_elem, "Start")
        # If it's a parsed appointment, convert back to ticks
        if 'start_ticks' in appointment:
            start_elem.text = appointment['start_ticks']
        else:
            # Convert from RFC3339 back to ticks
            start_elem.text = rfc3339_to_dotnet_ticks(appointment['start'])
        
        end_elem = etree.SubElement(appt_elem, "End")
        if 'end_ticks' in appointment:
            end_elem.text = appointment['end_ticks']
        else:
            end_elem.text = rfc3339_to_dotnet_ticks(appointment['end'])
        
        desc_elem = etree.SubElement(appt_elem, "Description")
        desc_elem.text = appointment['description']
        
        reminder_elem = etree.SubElement(appt_elem, "Reminder")
        reminder_elem.text = str(appointment['reminder'])
    
    # Write to file
    tree = etree.ElementTree(root)
    tree.write(xml_path, encoding='utf-8', xml_declaration=True, pretty_print=True)

def main():
    print("🚀 Starting calendar sync...")
    service = get_google_calendar_service()
    local_events = parse_local_xml(LOCAL_XML_PATH)
    google_events = get_google_events(service)
    
    print("\n📤 Syncing from XML to Google Calendar...")
    sync_xml_to_google(service, local_events, google_events)
    
    print("\n📥 Syncing from Google Calendar to XML...")
    sync_google_to_xml(google_events, local_events, LOCAL_XML_PATH)
    
    print("\n✅ Sync complete.")

if __name__ == '__main__':
    main()