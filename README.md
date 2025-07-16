# Calendar Sync for Tobii Dynavox Communicator

A bidirectional calendar synchronization application that keeps Google Calendar and Tobii Dynavox Communicator calendar in sync. This tool is specifically designed to help users of assistive communication technology maintain synchronized calendars across platforms.

## Overview

This application synchronizes calendar events between:
- **Google Calendar** 
- **Tobii Dynavox Communicator 5** local XML calendar files

The sync process is **bidirectional** and **intelligent**, detecting additions and deletions in both calendars and applying changes accordingly while preventing duplicates.

## Key Features

### 🔄 Bidirectional Synchronization
- **Google → Local**: New Google Calendar events are added to Tobii Dynavox Communicator
- **Local → Google**: New Tobii Dynavox events are added to Google Calendar
- **Deletions**: Events deleted from either calendar are removed from the other

### 🧠 Smart Change Detection
- Uses snapshot-based diff system to detect what has changed since last sync
- Prevents infinite sync loops by tracking event origins
- Handles time zone conversions between RFC3339 (Google) and .NET ticks (Tobii Dynavox)

### 🖥️ User-Friendly GUI
- PyQt5-based interface with real-time sync progress
- Large, accessible fonts suitable for assistive technology users
- Stay-on-top window for visibility
- Automatic Communicator launch after sync (configurable)

### ⚙️ Configurable Settings
- Adjustable time range for sync (past/future days)
- Optional automatic Communicator startup
- Persistent configuration storage
- Multiple XML file path support for different user profiles

## Installation

### Prerequisites
- Python 3.7+
- Google Calendar API credentials
- Tobii Dynavox Communicator 5 (for XML calendar files)

### Dependencies
```bash
pip install -r requirements.txt
```

Required packages:
- PyQt5 (GUI framework)
- google-auth-oauthlib (Google Calendar authentication)
- google-api-python-client (Google Calendar API)
- lxml (XML processing)
- appdirs (cross-platform config directories)

### Google Calendar Setup
1. Create a project in Google Cloud Console
2. Enable the Google Calendar API
3. Create OAuth2 credentials
4. Download `credentials.json` and place it in `src/secrets/credentials.json`

## Usage

### Running the Application
```bash
python src/main.py
```

### First Run
1. The app will open your browser for Google Calendar authentication
2. Grant necessary permissions
3. The sync process will begin automatically
4. View real-time progress in the GUI window

### Configuration
The app creates a configuration file in your system's app data directory:
- **Windows**: `%APPDATA%\CalendarSync\config.ini`
- **macOS**: `~/Library/Application Support/CalendarSync/config.ini`
- **Linux**: `~/.local/share/CalendarSync/config.ini`

#### Configuration Options
```ini
[DEFAULT]
FETCH_DAYS_FUTURE = 30    # Days ahead to sync
FETCH_DAYS_PAST = 7       # Days behind to sync
START_COMMUNICATOR = true # Auto-start Communicator after sync
```

## How It Works

### Sync Process
1. **Authentication**: Connects to Google Calendar using OAuth2
2. **Data Collection**: 
   - Fetches events from Google Calendar
   - Parses local XML calendar from Tobii Dynavox Communicator
3. **Change Detection**: 
   - Compares current state with previous snapshots
   - Identifies additions, deletions, and modifications
4. **Synchronization**:
   - Adds new events to both calendars
   - Removes deleted events from both calendars
   - Prevents duplicate syncing
5. **Snapshot Update**: Saves current state for next sync comparison

### File Locations

#### Tobii Dynavox XML Files
The app automatically searches for XML calendar files in:
- `C:\Users\[username]\AppData\Roaming\Tobii Dynavox\Communicator\5\Users\[profile]\Settings\Calendar\Appointments.xml`

#### Application Data
- **Snapshots**: `calendar_snapshots/` (tracks previous sync states)
- **Authentication**: `token.pkl` (Google OAuth tokens)
- **Configuration**: `config.ini` (user settings)

## Technical Details

### Time Conversion
- **Google Calendar**: Uses RFC3339 format (ISO 8601)
- **Tobii Dynavox**: Uses .NET ticks (100-nanosecond intervals since January 1, 0001 UTC)
- Automatic conversion between formats with timezone handling

### Event Matching
Events are matched by title/summary to detect duplicates and deletions:
- Google events use `summary` field
- XML events use `description` field
- Case-sensitive exact matching

### Sync Safeguards
- Events marked as "Synced from local XML" are not re-synced to prevent loops
- Failed operations are logged but don't stop the entire sync process
- Snapshots ensure only actual changes trigger sync operations

## Development

### Project Structure
```
src/
├── main.py              # Main application and GUI
├── auth.py              # Google Calendar authentication
├── event_manager.py     # Change detection and event operations
├── xml_handler.py       # XML parsing and writing
├── time_utils.py        # Time format conversions
└── snapshot_manager.py  # State tracking for change detection

test/
├── test_sync_calendar.py # Comprehensive test suite
├── conftest.py          # Test configuration
└── TESTING.md           # Testing documentation
```

### Running Tests
```bash
python -m pytest test/ -v
```

The test suite covers:
- Bidirectional sync operations
- Change detection logic
- Error handling
- Duplicate prevention

## Troubleshooting

### Common Issues

**"Cannot find XML file"**
- Ensure Tobii Dynavox Communicator 5 is installed
- Check that a user profile exists in Communicator
- Verify the XML file path in the application logs

**"Authentication failed"**
- Verify `credentials.json` is in the correct location
- Check Google Calendar API is enabled in Google Cloud Console
- Try deleting `token.pkl` to re-authenticate

**"Sync not working"**
- Check internet connection
- Verify Google Calendar permissions
- Review console output for specific error messages

### Debug Mode
Run with verbose output:
```bash
python src/main.py --verbose
```

## License

This project is designed to improve accessibility for users of assistive communication technology. Please ensure any usage complies with relevant accessibility and assistive technology guidelines.

## Contributing

When contributing, please:
1. Maintain accessibility-focused design principles
2. Test with various Tobii Dynavox Communicator configurations
3. Ensure proper error handling for assistive technology environments
4. Add tests for new functionality

## Support

For issues related to:
- **Google Calendar API**: Check Google Cloud Console documentation
- **Tobii Dynavox Communicator**: Contact Tobii Dynavox support
- **This application**: Review logs and test with minimal calendar data first