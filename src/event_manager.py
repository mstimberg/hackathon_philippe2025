from auth import CALENDAR_ID
from xml_handler import write_appointments_to_xml

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