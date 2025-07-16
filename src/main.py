import os
import pickle
import json
from datetime import datetime, timezone, timedelta
from lxml import etree
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'primary'
LOCAL_XML_PATH = 'Appointments.xml'
#LOCAL_XML_PATH_COMMUNICATOR = r'C:\Users\phili\AppData\Roaming\Tobii Dynavox\Communicator\5\Users\Philippe prédiction\Settings\Calendar'
FETCH_DAYS_FUTURE = 30
FETCH_DAYS_PAST = 7

# Snapshot files to track previous states
SNAPSHOT_DIR = 'calendar_snapshots'
GOOGLE_SNAPSHOT_FILE = os.path.join(SNAPSHOT_DIR, 'google_events.json')
XML_SNAPSHOT_FILE = os.path.join(SNAPSHOT_DIR, 'xml_events.json')

def ensure_snapshot_dir():
    """Create snapshot directory if it doesn't exist."""
    if not os.path.exists(SNAPSHOT_DIR):
        os.makedirs(SNAPSHOT_DIR)

def save_snapshots(google_events, xml_events):
    """Save current states as snapshots for next sync comparison."""
    ensure_snapshot_dir()
    
    # Save Google events snapshot
    with open(GOOGLE_SNAPSHOT_FILE, 'w', encoding='utf-8') as f:
        json.dump(google_events, f, indent=2, ensure_ascii=False)
    
    # Save XML events snapshot
    with open(XML_SNAPSHOT_FILE, 'w', encoding='utf-8') as f:
        json.dump(xml_events, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Saved snapshots: {len(google_events)} Google events, {len(xml_events)} XML events")

def load_snapshots():
    """Load previous snapshots. Returns empty lists if no snapshots exist."""
    google_snapshot = []
    xml_snapshot = []
    
    try:
        if os.path.exists(GOOGLE_SNAPSHOT_FILE):
            with open(GOOGLE_SNAPSHOT_FILE, 'r', encoding='utf-8') as f:
                google_snapshot = json.load(f)
        
        if os.path.exists(XML_SNAPSHOT_FILE):
            with open(XML_SNAPSHOT_FILE, 'r', encoding='utf-8') as f:
                xml_snapshot = json.load(f)
                
        print(f"📁 Loaded snapshots: {len(google_snapshot)} Google events, {len(xml_snapshot)} XML events")
    except Exception as e:
        print(f"⚠️ Error loading snapshots: {e}")
    
    return google_snapshot, xml_snapshot

def get_event_key(event, source='google'):
    """Generate a unique key for an event to track it across syncs."""
    if source == 'google':
        return event.get('summary', '').strip()
    else:  # xml
        return event.get('description', '').strip()

def detect_changes(current_events, previous_events, source='google'):
    """
    Detect additions, deletions, and modifications between current and previous events.
    Returns: (added, deleted, modified)
    """
    current_keys = {get_event_key(event, source): event for event in current_events}
    previous_keys = {get_event_key(event, source): event for event in previous_events}
    
    added = [event for key, event in current_keys.items() if key not in previous_keys]
    deleted = [event for key, event in previous_keys.items() if key not in current_keys]
    
    # For now, we'll focus on additions and deletions. Modifications can be added later.
    modified = []
    
    return added, deleted, modified

def get_google_calendar_service():
    creds = None
    if os.path.exists('token.pkl'):
        with open('token.pkl', 'rb') as token:
            creds = pickle.load(token)
    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file(os.path.join(os.path.dirname(__file__), 'secrets', 'credentials.json'), SCOPES)
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

def get_events_past_week_to_next_month(service):
    """
    Get events from one week ago to one month from now.
    """
    now = datetime.now(timezone.utc)
    
    # One week ago
    time_min = (now - timedelta(days=FETCH_DAYS_PAST)).isoformat()
    
    # One month from now (approximately 30 days)
    time_max = (now + timedelta(days=FETCH_DAYS_FUTURE)).isoformat()
    
    print(f"📅 Fetching events from {time_min[:10]} to {time_max[:10]}")
    
    return get_google_events(service, time_min=time_min, time_max=time_max)

def sync_xml_to_google(service, local_events, google_events):
    # Filter local events to the same time range (past week to next month)
    now = datetime.now(timezone.utc)
    time_min = now - timedelta(days=FETCH_DAYS_PAST)
    time_max = now + timedelta(days=FETCH_DAYS_FUTURE)
    
    filtered_local_events = []
    for event in local_events:
        try:
            # Parse the event start time
            event_start = datetime.fromisoformat(event['start'].replace('Z', '+00:00'))
            if event_start.tzinfo is None:
                event_start = event_start.replace(tzinfo=timezone.utc)
            else:
                event_start = event_start.astimezone(timezone.utc)
            
            # Check if the event falls within our time range
            if time_min <= event_start <= time_max:
                filtered_local_events.append(event)
        except Exception as e:
            print(f"⚠️ Error parsing date for event '{event.get('description', 'Unknown')}': {e}")
            continue
    
    print(f"🔍 Filtered {len(filtered_local_events)} XML events (out of {len(local_events)}) within time range")
    
    google_event_titles = {e.get('summary', ''): e for e in google_events}
    for local_event in filtered_local_events:
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

def sync_calendar():
    """
    Perform the calendar synchronization between XML and Google Calendar.
    """
    print("🚀 Starting calendar sync...")
    service = get_google_calendar_service()
    local_events = parse_local_xml(LOCAL_XML_PATH)
    
    # Use the same time filter for sync as for display
    google_events = get_events_past_week_to_next_month(service)
    
    print("\n📤 Syncing from XML to Google Calendar...")
    sync_xml_to_google(service, local_events, google_events)
    
    print("\n📥 Syncing from Google Calendar to XML...")
    sync_google_to_xml(google_events, local_events, LOCAL_XML_PATH)
    
    print("\n✅ Sync complete.")

def delete_google_events(service, events_to_delete):
    """Delete events from Google Calendar."""
    for event in events_to_delete:
        try:
            # Extract title based on event source
            # XML events use 'description', Google events use 'summary'
            title = event.get('description', '').strip() or event.get('summary', '').strip()
            
            if not title:
                print(f"⚠️ Cannot delete event with empty title: {event}")
                continue
            
            # Get current events to find the one to delete
            events_result = service.events().list(
                calendarId=CALENDAR_ID,
                q=title,
                maxResults=10
            ).execute()
            
            google_events = events_result.get('items', [])
            
            for google_event in google_events:
                if google_event.get('summary', '').strip() == title:
                    service.events().delete(
                        calendarId=CALENDAR_ID,
                        eventId=google_event['id']
                    ).execute()
                    print(f"🗑️ Deleted from Google Calendar: {title}")
                    break
            else:
                print(f"⚠️ Could not find event to delete in Google Calendar: {title}")
                
        except Exception as e:
            print(f"❌ Error deleting Google event '{title if 'title' in locals() else 'Unknown'}': {e}")

def delete_xml_events(xml_events, events_to_delete, xml_path):
    """Remove events from XML list and rewrite the file."""
    # Extract titles properly from both Google events (summary) and XML events (description)
    titles_to_delete = set()
    for event in events_to_delete:
        title = event.get('summary', '').strip() or event.get('description', '').strip()
        if title:
            titles_to_delete.add(title)
            print(f"🔍 Looking to delete from XML: {title}")
    
    # Filter out events that should be deleted
    remaining_events = []
    deleted_count = 0
    
    for event in xml_events:
        xml_title = event.get('description', '').strip()
        if xml_title in titles_to_delete:
            print(f"🗑️ Deleted from XML: {xml_title}")
            deleted_count += 1
        else:
            remaining_events.append(event)
    
    if deleted_count > 0:
        # Rewrite the XML file with remaining events
        write_appointments_to_xml(remaining_events, xml_path)
        print(f"✅ Removed {deleted_count} events from XML")
    else:
        print(f"ℹ️ No matching events found to delete from XML")
    
    return remaining_events

def sync_calendar_with_diff():
    """
    Perform diff-based calendar synchronization that handles additions and deletions.
    """
    print("🚀 Starting diff-based calendar sync...")
    service = get_google_calendar_service()
    
    # Load current states
    current_xml_events = parse_local_xml(LOCAL_XML_PATH)
    current_google_events = get_events_past_week_to_next_month(service)
    
    # Filter XML events to same time range
    now = datetime.now(timezone.utc)
    time_min = now - timedelta(days=FETCH_DAYS_PAST)
    time_max = now + timedelta(days=FETCH_DAYS_FUTURE)
    
    filtered_xml_events = []
    for event in current_xml_events:
        try:
            event_start = datetime.fromisoformat(event['start'].replace('Z', '+00:00'))
            if event_start.tzinfo is None:
                event_start = event_start.replace(tzinfo=timezone.utc)
            else:
                event_start = event_start.astimezone(timezone.utc)
            
            if time_min <= event_start <= time_max:
                filtered_xml_events.append(event)
        except Exception:
            continue
    
    # Load previous snapshots
    prev_google_events, prev_xml_events = load_snapshots()
    
    # Detect changes
    google_added, google_deleted, _ = detect_changes(current_google_events, prev_google_events, 'google')
    xml_added, xml_deleted, _ = detect_changes(filtered_xml_events, prev_xml_events, 'xml')
    
    print(f"\n📊 Change Detection:")
    print(f"   Google: +{len(google_added)} -{len(google_deleted)}")
    print(f"   XML: +{len(xml_added)} -{len(xml_deleted)}")
    
    # Apply changes: XML additions → Google Calendar
    if xml_added:
        print(f"\n📤 Adding {len(xml_added)} XML events to Google Calendar...")
        google_event_titles = {e.get('summary', ''): e for e in current_google_events}
        for event in xml_added:
            title = event['description']
            if title not in google_event_titles:
                try:
                    event_body = {
                        'summary': event['description'],
                        'start': {
                            'dateTime': event['start'],
                            'timeZone': 'Europe/Paris',
                        },
                        'end': {
                            'dateTime': event['end'],
                            'timeZone': 'Europe/Paris',
                        },
                        'description': f"Synced from local XML - ID {event['id']}"
                    }
                    created = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
                    print(f"✅ Added to Google: {created['summary']}")
                except Exception as e:
                    print(f"❌ Failed to add to Google: {title} - {e}")
    
    # Apply changes: Google additions → XML
    if google_added:
        print(f"\n📥 Adding {len(google_added)} Google events to XML...")
        xml_descriptions = {event['description'].strip() for event in current_xml_events}
        existing_ids = [int(event['id']) for event in current_xml_events if event['id'].isdigit()]
        next_id = max(existing_ids) + 1 if existing_ids else 1
        
        new_xml_events = []
        for event in google_added:
            summary = event.get('summary', '').strip()
            description = event.get('description', '')
            
            # Skip if already exists or was synced from XML
            if summary in xml_descriptions or "Synced from local XML" in description:
                continue
            
            # Extract start and end times
            start_time = event.get('start', {})
            end_time = event.get('end', {})
            start_datetime = start_time.get('dateTime') or start_time.get('date')
            end_datetime = end_time.get('dateTime') or end_time.get('date')
            
            if start_datetime and end_datetime:
                new_xml_events.append({
                    'id': str(next_id),
                    'start_ticks': rfc3339_to_dotnet_ticks(start_datetime),
                    'end_ticks': rfc3339_to_dotnet_ticks(end_datetime),
                    'description': summary,
                    'reminder': False
                })
                print(f"✅ Added to XML: {summary}")
                next_id += 1
        
        if new_xml_events:
            write_appointments_to_xml(current_xml_events + new_xml_events, LOCAL_XML_PATH)
            current_xml_events.extend(new_xml_events)
    
    # Handle deletions: XML deletions → Google Calendar
    if xml_deleted:
        print(f"\n🗑️ Removing {len(xml_deleted)} events from Google Calendar...")
        delete_google_events(service, xml_deleted)
    
    # Handle deletions: Google deletions → XML  
    if google_deleted:
        print(f"\n🗑️ Removing {len(google_deleted)} events from XML...")
        current_xml_events = delete_xml_events(current_xml_events, google_deleted, LOCAL_XML_PATH)
    
    # Refresh current states after all changes
    final_google_events = get_events_past_week_to_next_month(service)
    final_xml_events = parse_local_xml(LOCAL_XML_PATH)
    
    # Filter XML events again for snapshot
    final_filtered_xml = []
    for event in final_xml_events:
        try:
            event_start = datetime.fromisoformat(event['start'].replace('Z', '+00:00'))
            if event_start.tzinfo is None:
                event_start = event_start.replace(tzinfo=timezone.utc)
            else:
                event_start = event_start.astimezone(timezone.utc)
            
            if time_min <= event_start <= time_max:
                final_filtered_xml.append(event)
        except Exception:
            continue
    
    # Save snapshots for next sync
    save_snapshots(final_google_events, final_filtered_xml)
    
    print("\n✅ Diff-based sync complete!")

def reset_snapshots():
    """Reset snapshots - useful for debugging or starting fresh."""
    try:
        if os.path.exists(GOOGLE_SNAPSHOT_FILE):
            os.remove(GOOGLE_SNAPSHOT_FILE)
        if os.path.exists(XML_SNAPSHOT_FILE):
            os.remove(XML_SNAPSHOT_FILE)
        if os.path.exists(SNAPSHOT_DIR) and not os.listdir(SNAPSHOT_DIR):
            os.rmdir(SNAPSHOT_DIR)
        print("🔄 Snapshots reset successfully. Next sync will be treated as initial sync.")
    except Exception as e:
        print(f"❌ Error resetting snapshots: {e}")


def main():
    sync_calendar_with_diff()

if __name__ == '__main__':
    main()