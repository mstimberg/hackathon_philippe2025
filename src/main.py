from datetime import datetime
from auth import get_google_calendar_service, get_events_past_week_to_next_month, CALENDAR_ID
from time_utils import filter_events_by_time_range
from xml_handler import parse_local_xml, write_appointments_to_xml
from time_utils import rfc3339_to_dotnet_ticks
from snapshot_manager import save_snapshots, load_snapshots
from event_manager import detect_changes, delete_google_events, delete_xml_events
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QPushButton
from PyQt5.QtCore import Qt, QRunnable
from PyQt5 import QtCore
import sys, os
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtCore import QObject, pyqtSignal, QThreadPool
from appdirs import user_config_dir
import configparser
STYLE = """
QWidget {
   font-size: 30px;
   font-family: Helvetica, Arial;
}
"""

# Configuration
LOCAL_XML_PATH = 'Appointments.xml'
XML_PATHS_COMMUNICATOR = [r'C:\Users\phili\AppData\Roaming\Tobii Dynavox\Communicator\5\Users\Philippe prédiction\Settings\Calendar\Appointments.xml',
                          r'C:\Users\Philippe\AppData\Roaming\Tobii Dynavox\Communicator\5\Users\Philippe\Settings\Calendar\Appointments.xml']
config_dir = user_config_dir("CalendarSync", roaming=True)
try:
    print("reading config from", os.path.join(config_dir, "config.ini"))
    parser = configparser.ConfigParser()
    parser.read(os.path.join(config_dir, "config.ini"))
    FETCH_DAYS_FUTURE = int(parser["DEFAULT"]["FETCH_DAYS_FUTURE"])
    FETCH_DAYS_PAST = int(parser["DEFAULT"]["FETCH_DAYS_PAST"])
except Exception as ex:
    print("Did not manage to parse config file: ", str(ex))
    FETCH_DAYS_FUTURE = 1
    FETCH_DAYS_PAST = 1

# Load current states
for path in XML_PATHS_COMMUNICATOR:
    if os.path.exists(path):
        XML_PATH = path
        break
else:
    print("Using local test file")
    XML_PATH = LOCAL_XML_PATH

# ============================================================================
# SYNC LOGIC - SIMPLE SYNC (ADDITIONS ONLY)
# ============================================================================

def sync_xml_to_google(service, local_events, google_events):
    """Sync XML events to Google Calendar (additions only)."""
    # Filter local events to the same time range (past week to next month)
    filtered_local_events = filter_events_by_time_range(
        local_events, FETCH_DAYS_PAST, FETCH_DAYS_FUTURE
    )
        
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
            print(f"✅ Evénement créé: {created['summary']} à {created['start']['dateTime']}")
        else:
            print(f"🔁 Evénement déjà existant: {title}")

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
            print(f"🔁 Evénement déjà existant dans le calendrier local : {summary}")
            continue
        
        # Extract start and end times
        start_time = google_event.get('start', {})
        end_time = google_event.get('end', {})
        
        # Handle both dateTime and date fields
        start_datetime = start_time.get('dateTime') or start_time.get('date')
        end_datetime = end_time.get('dateTime') or end_time.get('date')
        
        if not start_datetime or not end_datetime:
            print(f"⚠️ Événement sans date/heure: {summary}")
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
        
        print(f"📅 Nouveau rendez-vous depuis Google: {summary}")
        next_id += 1
    
    if new_appointments:
        # Update the XML file
        write_appointments_to_xml(local_events + new_appointments, xml_path)
        print(f"✅ Ajouté {len(new_appointments)} nouveaux rendez-vous au calendrier local ")
    else:
        print("ℹ️ Aucun nouveau rendez-vous à ajouter au calendrier local ")

# ============================================================================
# SYNC LOGIC - DIFF-BASED SYNC (ADDITIONS AND DELETIONS)
# ============================================================================

def sync_calendar_with_diff():
    """Perform diff-based calendar synchronization that handles additions and deletions."""
    service = get_google_calendar_service()
    
    current_xml_events = parse_local_xml(XML_PATH)
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
    
    # Apply changes: XML additions → Google Calendar
    if xml_added:
        print(f"\n📤 Ajout de {len(xml_added)} événements du calendrier local  au calendrier Google...")
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
                    print(f"✅ Ajouté au calendrier Google: {created['summary']}")
                except Exception as e:
                    print(f"❌ Échec de l'ajout au calendrier Google: {title} - {e}")
    
    # Apply changes: Google additions → XML
    if google_added:
        print(f"\n📥 Ajout de {len(google_added)} événements du calendrier Google au calendrier local...")
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
                print(f"✅ Ajouté au calendrier local: {summary}")
                next_id += 1
        
        if new_xml_events:
            write_appointments_to_xml(current_xml_events + new_xml_events, XML_PATH)
            current_xml_events.extend(new_xml_events)
    
    # Handle deletions: XML deletions → Google Calendar
    if xml_deleted:
        print(f"\n🗑️ Suppression de {len(xml_deleted)} événements du calendrier Google...")
        for event in xml_deleted:
            print(f"Suppression de l'événement {event['summary']} du calendrier Google")
        delete_google_events(service, xml_deleted)
    
    # Handle deletions: Google deletions → XML  
    if google_deleted:
        print(f"\n🗑️ Suppression de {len(google_deleted)} événements du calendrier local...")
        for event in google_deleted:
            print(f"Suppression de l'événement {event['summary']} du calendrier local")
        current_xml_events = delete_xml_events(current_xml_events, google_deleted, XML_PATH)
    
    # Refresh current states after all changes
    final_google_events = get_events_past_week_to_next_month(service, FETCH_DAYS_PAST, FETCH_DAYS_FUTURE)
    final_xml_events = parse_local_xml(XML_PATH)
    
    # Filter XML events again for snapshot
    final_filtered_xml = filter_events_by_time_range(
        final_xml_events, FETCH_DAYS_PAST, FETCH_DAYS_FUTURE
    )
    
    # Save snapshots for next sync
    save_snapshots(final_google_events, final_filtered_xml)

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
        # Auto-scroll to bottom using ensureCursorVisible
        self.text_area.ensureCursorVisible()
    
    @QtCore.pyqtSlot()
    def sync_finished(self):
        """Signal that sync is finished, enable close button."""
        self.close_button.setEnabled(True)
        self.append_text("<br><b>✅ Synchronisation terminée. Vous pouvez maintenant fermer cette fenêtre.</b>")


class Signals(QObject):
    log_text = pyqtSignal(str)
    sync_finished = pyqtSignal()

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
            self.signals.sync_finished.connect(dialog.sync_finished)
        
        def run(self):
            # Ugly quick fix to get print statements into dialog
            globals()["print"] = self.signals.log_text.emit
            try:
                main()
            except Exception as ex:
                print("Erreur: " + str(ex))
            self.signals.sync_finished.emit()
    
    # Run main in background thread
    pool = QThreadPool.globalInstance()
    pool.start(SyncRunner(dialog))
    
    sys.exit(app.exec_())
