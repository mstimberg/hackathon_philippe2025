import os
from datetime import datetime, timezone, timedelta
from auth import get_google_calendar_service, get_events_past_week_to_next_month, CALENDAR_ID
from time_utils import filter_events_by_time_range
from xml_handler import parse_local_xml, write_appointments_to_xml
from time_utils import rfc3339_to_dotnet_ticks
from snapshot_manager import save_snapshots, load_snapshots, reset_snapshots
from event_manager import detect_changes, delete_google_events, delete_xml_events
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import Qt, QRunnable
from PyQt5 import QtCore
import sys
from PyQt5.QtWidgets import QTextEdit
from contextlib import redirect_stdout
from PyQt5.QtCore import QObject, pyqtSignal, QThreadPool

STYLE = """
QWidget {
   font-size: 30px;
   font-family: "Noto Sans", Arial, Helvetica, sans-serif;
}
"""

# Configuration
LOCAL_XML_PATH = 'Appointments.xml'
#LOCAL_XML_PATH_COMMUNICATOR = r'C:\Users\phili\AppData\Roaming\Tobii Dynavox\Communicator\5\Users\Philippe prédiction\Settings\Calendar'
FETCH_DAYS_FUTURE = 30
FETCH_DAYS_PAST = 7

# ============================================================================
# SYNC LOGIC - SIMPLE SYNC (ADDITIONS ONLY)
# ============================================================================

def sync_xml_to_google(service, local_events, google_events):
    """Sync XML events to Google Calendar (additions only)."""
    # Filter local events to the same time range (past week to next month)
    filtered_local_events = filter_events_by_time_range(
        local_events, FETCH_DAYS_PAST, FETCH_DAYS_FUTURE
    )
    
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
    """Sync Google Calendar events to XML (additions only)."""
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

# ============================================================================
# SYNC LOGIC - DIFF-BASED SYNC (ADDITIONS AND DELETIONS)
# ============================================================================

def sync_calendar_with_diff():
    """Perform diff-based calendar synchronization that handles additions and deletions."""
    service = get_google_calendar_service()
    
    # Load current states
    current_xml_events = parse_local_xml(LOCAL_XML_PATH)
    current_google_events = get_events_past_week_to_next_month(service, FETCH_DAYS_PAST, FETCH_DAYS_FUTURE)
    
    # Filter XML events to same time range
    filtered_xml_events = filter_events_by_time_range(
        current_xml_events, FETCH_DAYS_PAST, FETCH_DAYS_FUTURE
    )
    
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
        print(f"\n📥 Adding {len(google_added)} Google events to Local Calendar (XML format)...")
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
                print(f"✅ Added to Local Calendar (XML format): {summary}")
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
    final_google_events = get_events_past_week_to_next_month(service, FETCH_DAYS_PAST, FETCH_DAYS_FUTURE)
    final_xml_events = parse_local_xml(LOCAL_XML_PATH)
    
    # Filter XML events again for snapshot
    final_filtered_xml = filter_events_by_time_range(
        final_xml_events, FETCH_DAYS_PAST, FETCH_DAYS_FUTURE
    )
    
    # Save snapshots for next sync
    save_snapshots(final_google_events, final_filtered_xml)

# ============================================================================
# DISPLAY FUNCTIONS
# ============================================================================

def filter_and_display_events():
    """Filter and display events from past week to next month."""
    print("🔍 Filtering events from past week to next month...")
    service = get_google_calendar_service()
    filtered_events = get_events_past_week_to_next_month(service, FETCH_DAYS_PAST, FETCH_DAYS_FUTURE)
    
    if not filtered_events:
        print("📭 No events found in the specified time range.")
        return
    
    print(f"\n📅 Found {len(filtered_events)} events:")
    print("-" * 80)
    
    for event in filtered_events:
        summary = event.get('summary', 'No title')
        start_time = event.get('start', {})
        end_time = event.get('end', {})
        
        # Handle both dateTime and date fields
        start_datetime = start_time.get('dateTime') or start_time.get('date')
        end_datetime = end_time.get('dateTime') or end_time.get('date')
        
        # Format the datetime for display
        if start_datetime:
            try:
                if 'T' in start_datetime:  # Full datetime
                    start_dt = datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
                    formatted_start = start_dt.strftime('%Y-%m-%d %H:%M')
                else:  # Date only
                    formatted_start = start_datetime
            except:
                formatted_start = start_datetime
        else:
            formatted_start = "Unknown time"
        
        print(f"🗓️  {summary}")
        print(f"   📅 {formatted_start}")
        
        # Add description if available
        description = event.get('description', '')
        if description and len(description) < 100:
            print(f"   📝 {description}")
        
        print()

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    sync_calendar_with_diff()


class SyncLogDialog(QDialog):
    """Dialog to display sync logs with a close button."""
    
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setWindowTitle("Synchronisation Agenda")
        self.setMinimumSize(800, 600)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Create rich text area
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        layout.addWidget(self.text_area)
        
        # Create close button (initially disabled)
        self.close_button = QPushButton("Fermer")
        self.close_button.clicked.connect(self.accept)
        self.close_button.setEnabled(False)
        self.close_button.setMinimumHeight(40)
        layout.addWidget(self.close_button)
    
    @QtCore.pyqtSlot(str)
    def append_text(self, text=None):
        """Append text to the text area."""
        self.text_area.append(text)
        # Auto-scroll to bottom
        cursor = self.text_area.textCursor()
        cursor.movePosition(cursor.End)
        self.text_area.setTextCursor(cursor)
    
    @QtCore.pyqtSlot()
    def sync_finished(self):
        """Signal that sync is finished, enable close button."""
        self.close_button.setEnabled(True)
        self.append_text("<br><b>✅ Sync complete. You can now close this window.</b>")


class Signals(QObject):
    log_text = pyqtSignal(str)

if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    dialog = SyncLogDialog()
    dialog.show()
    class SyncRunner(QRunnable):
        
        def __init__(self, dialog):
            super().__init__()
            self.dialog = dialog
            self.signals = Signals()
            self.signals.log_text.connect(dialog.append_text)
        
        def run(self):
            # Ugly quick fix to get print statements into dialog
            globals()["print"] = self.signals.log_text.emit 
            main()
            self.dialog.sync_finished()
    
    # Run main in background thread
    pool = QThreadPool.globalInstance()
    pool.start(SyncRunner(dialog))
    
    sys.exit(app.exec_())
