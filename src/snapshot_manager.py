import os
import json

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
                
    except Exception as e:
        print(f"⚠️ Error loading snapshots: {e}")
    
    return google_snapshot, xml_snapshot

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