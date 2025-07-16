import pytest
from unittest.mock import Mock, patch, call
from datetime import datetime, timezone
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.main import sync_calendar_with_diff


@pytest.mark.unit
class TestSyncCalendarWithDiff:
    """Test suite for sync_calendar_with_diff function."""

    @pytest.fixture
    def mock_google_service(self):
        """Mock Google Calendar service."""
        service = Mock()
        
        # Create a mock events manager
        events_mock = Mock()
        service.events.return_value = events_mock
        
        # Create a mock insert method
        insert_mock = Mock()
        events_mock.insert.return_value = insert_mock
        
        # Mock the execute method
        insert_mock.execute.return_value = {
            'summary': 'Test Event',
            'start': {'dateTime': '2024-01-15T10:00:00+00:00'}
        }
        
        return service

    @pytest.fixture
    def sample_xml_events(self):
        """Sample XML events for testing."""
        return [
            {
                'id': '1',
                'start': '2024-01-15T09:00:00+00:00',
                'end': '2024-01-15T10:00:00+00:00',
                'description': 'Doctor Appointment',
                'reminder': True
            },
            {
                'id': '2',
                'start': '2024-01-16T14:00:00+00:00',
                'end': '2024-01-16T15:00:00+00:00',
                'description': 'Meeting with Team',
                'reminder': False
            }
        ]

    @pytest.fixture
    def sample_google_events(self):
        """Sample Google Calendar events for testing."""
        return [
            {
                'id': 'google_1',
                'summary': 'Google Meeting',
                'start': {'dateTime': '2024-01-17T11:00:00+00:00'},
                'end': {'dateTime': '2024-01-17T12:00:00+00:00'},
                'description': 'Team standup'
            },
            {
                'id': 'google_2',
                'summary': 'Lunch Break',
                'start': {'dateTime': '2024-01-18T12:00:00+00:00'},
                'end': {'dateTime': '2024-01-18T13:00:00+00:00'},
                'description': ''
            }
        ]

    @pytest.fixture
    def empty_snapshots(self):
        """Empty previous snapshots for initial sync testing."""
        return [], []

    @pytest.fixture
    def snapshots_with_existing_data(self, sample_xml_events, sample_google_events):
        """Snapshots with existing data for change detection."""
        return sample_google_events[:1], sample_xml_events[:1]

    @patch('src.main.save_snapshots')
    @patch('src.main.get_events_past_week_to_next_month')
    @patch('src.main.parse_local_xml')
    @patch('src.main.filter_events_by_time_range')
    @patch('src.main.load_snapshots')
    @patch('src.main.detect_changes')
    @patch('src.main.write_appointments_to_xml')
    @patch('src.main.rfc3339_to_dotnet_ticks')
    @patch('src.main.get_google_calendar_service')
    def test_xml_additions_sync_to_google(
        self,
        mock_get_service,
        mock_rfc3339_to_ticks,
        mock_write_xml,
        mock_detect_changes,
        mock_load_snapshots,
        mock_filter_events,
        mock_parse_xml,
        mock_get_google_events,
        mock_save_snapshots,
        mock_google_service,
        sample_xml_events,
        sample_google_events,
        empty_snapshots
    ):
        """Test that new XML events are properly synced to Google Calendar."""
        # Setup mocks
        mock_get_service.return_value = mock_google_service
        mock_parse_xml.return_value = sample_xml_events
        mock_get_google_events.return_value = sample_google_events
        mock_filter_events.return_value = sample_xml_events
        mock_load_snapshots.return_value = empty_snapshots
        mock_rfc3339_to_ticks.return_value = '637776648000000000'
        
        # New XML event added (not in previous snapshots)
        new_xml_event = {
            'id': '3',
            'start': '2024-01-19T15:00:00+00:00',
            'end': '2024-01-19T16:00:00+00:00',
            'description': 'New XML Event',
            'reminder': True
        }
        
        # Mock detect_changes to return new XML event as added
        mock_detect_changes.side_effect = [
            ([], [], []),  # Google changes (no changes)
            ([new_xml_event], [], [])  # XML changes (one addition)
        ]
        
        # Execute the function
        sync_calendar_with_diff()
        
        # Verify Google Calendar API was called to create event
        events_mock = mock_google_service.events.return_value
        events_mock.insert.assert_called_once()
        insert_call = events_mock.insert.call_args
        
        # Verify the event data sent to Google
        assert insert_call[1]['calendarId'] == 'primary'
        event_body = insert_call[1]['body']
        assert event_body['summary'] == 'New XML Event'
        assert event_body['start']['dateTime'] == '2024-01-19T15:00:00+00:00'
        assert event_body['end']['dateTime'] == '2024-01-19T16:00:00+00:00'
        assert 'Synced from local XML - ID 3' in event_body['description']
        
        # Verify snapshots were saved
        mock_save_snapshots.assert_called_once()

    @patch('src.main.save_snapshots')
    @patch('src.main.get_events_past_week_to_next_month')
    @patch('src.main.parse_local_xml')
    @patch('src.main.filter_events_by_time_range')
    @patch('src.main.load_snapshots')
    @patch('src.main.detect_changes')
    @patch('src.main.write_appointments_to_xml')
    @patch('src.main.rfc3339_to_dotnet_ticks')
    @patch('src.main.get_google_calendar_service')
    def test_google_additions_sync_to_xml(
        self,
        mock_get_service,
        mock_rfc3339_to_ticks,
        mock_write_xml,
        mock_detect_changes,
        mock_load_snapshots,
        mock_filter_events,
        mock_parse_xml,
        mock_get_google_events,
        mock_save_snapshots,
        mock_google_service,
        sample_xml_events,
        sample_google_events,
        empty_snapshots
    ):
        """Test that new Google Calendar events are properly synced to XML."""
        # Setup mocks
        mock_get_service.return_value = mock_google_service
        mock_parse_xml.return_value = sample_xml_events
        mock_get_google_events.return_value = sample_google_events
        mock_filter_events.return_value = sample_xml_events
        mock_load_snapshots.return_value = empty_snapshots
        mock_rfc3339_to_ticks.return_value = '637776648000000000'
        
        # New Google event added
        new_google_event = {
            'id': 'google_new',
            'summary': 'New Google Event',
            'start': {'dateTime': '2024-01-20T10:00:00+00:00'},
            'end': {'dateTime': '2024-01-20T11:00:00+00:00'},
            'description': 'Meeting from Google'
        }
        
        # Mock detect_changes to return new Google event as added
        mock_detect_changes.side_effect = [
            ([new_google_event], [], []),  # Google changes (one addition)
            ([], [], [])  # XML changes (no changes)
        ]
        
        # Execute the function
        sync_calendar_with_diff()
        
        # Verify XML was updated with new event
        mock_write_xml.assert_called()
        write_call_args = mock_write_xml.call_args[0]
        updated_events = write_call_args[0]
        
        # Find the new event in the updated XML events
        new_xml_event = None
        for event in updated_events:
            if event.get('description') == 'New Google Event':
                new_xml_event = event
                break
        
        assert new_xml_event is not None, "New Google event should be added to XML"
        assert new_xml_event['description'] == 'New Google Event'
        assert new_xml_event['reminder'] == False  # Default for Google events
        assert mock_rfc3339_to_ticks.called  # Time conversion should happen
        
        # Verify snapshots were saved
        mock_save_snapshots.assert_called_once()

    @patch('src.main.save_snapshots')
    @patch('src.main.get_events_past_week_to_next_month')
    @patch('src.main.parse_local_xml')
    @patch('src.main.filter_events_by_time_range')
    @patch('src.main.load_snapshots')
    @patch('src.main.detect_changes')
    @patch('src.main.delete_google_events')
    @patch('src.main.get_google_calendar_service')
    def test_xml_deletions_sync_to_google(
        self,
        mock_get_service,
        mock_delete_google,
        mock_detect_changes,
        mock_load_snapshots,
        mock_filter_events,
        mock_parse_xml,
        mock_get_google_events,
        mock_save_snapshots,
        mock_google_service,
        sample_xml_events,
        sample_google_events,
        snapshots_with_existing_data
    ):
        """Test that deleted XML events are properly removed from Google Calendar."""
        # Setup mocks
        mock_get_service.return_value = mock_google_service
        mock_parse_xml.return_value = sample_xml_events[1:]  # One event removed
        mock_get_google_events.return_value = sample_google_events
        mock_filter_events.return_value = sample_xml_events[1:]
        mock_load_snapshots.return_value = snapshots_with_existing_data
        
        # Deleted XML event
        deleted_xml_event = sample_xml_events[0]  # First event was deleted
        
        # Mock detect_changes to return deleted XML event
        mock_detect_changes.side_effect = [
            ([], [], []),  # Google changes (no changes)
            ([], [deleted_xml_event], [])  # XML changes (one deletion)
        ]
        
        # Execute the function
        sync_calendar_with_diff()
        
        # Verify delete_google_events was called with the deleted event
        mock_delete_google.assert_called_once_with(mock_google_service, [deleted_xml_event])
        
        # Verify snapshots were saved
        mock_save_snapshots.assert_called_once()

    @patch('src.main.save_snapshots')
    @patch('src.main.get_events_past_week_to_next_month')
    @patch('src.main.parse_local_xml')
    @patch('src.main.filter_events_by_time_range')
    @patch('src.main.load_snapshots')
    @patch('src.main.detect_changes')
    @patch('src.main.delete_xml_events')
    @patch('src.main.get_google_calendar_service')
    def test_google_deletions_sync_to_xml(
        self,
        mock_get_service,
        mock_delete_xml,
        mock_detect_changes,
        mock_load_snapshots,
        mock_filter_events,
        mock_parse_xml,
        mock_get_google_events,
        mock_save_snapshots,
        mock_google_service,
        sample_xml_events,
        sample_google_events,
        snapshots_with_existing_data
    ):
        """Test that deleted Google Calendar events are properly removed from XML."""
        # Setup mocks
        mock_get_service.return_value = mock_google_service
        mock_parse_xml.return_value = sample_xml_events
        mock_get_google_events.return_value = sample_google_events[1:]  # One event removed
        mock_filter_events.return_value = sample_xml_events
        mock_load_snapshots.return_value = snapshots_with_existing_data
        mock_delete_xml.return_value = sample_xml_events  # Return updated list
        
        # Deleted Google event
        deleted_google_event = sample_google_events[0]  # First event was deleted
        
        # Mock detect_changes to return deleted Google event
        mock_detect_changes.side_effect = [
            ([], [deleted_google_event], []),  # Google changes (one deletion)
            ([], [], [])  # XML changes (no changes)
        ]
        
        # Execute the function
        sync_calendar_with_diff()
        
        # Verify delete_xml_events was called with the deleted event
        mock_delete_xml.assert_called_once()
        delete_call_args = mock_delete_xml.call_args[0]
        assert delete_call_args[0] == sample_xml_events  # Current XML events
        assert delete_call_args[1] == [deleted_google_event]  # Events to delete
        assert delete_call_args[2] == 'Appointments.xml'  # XML path
        
        # Verify snapshots were saved
        mock_save_snapshots.assert_called_once()

    @patch('src.main.save_snapshots')
    @patch('src.main.get_events_past_week_to_next_month')
    @patch('src.main.parse_local_xml')
    @patch('src.main.filter_events_by_time_range')
    @patch('src.main.load_snapshots')
    @patch('src.main.detect_changes')
    @patch('src.main.get_google_calendar_service')
    def test_no_changes_detected(
        self,
        mock_get_service,
        mock_detect_changes,
        mock_load_snapshots,
        mock_filter_events,
        mock_parse_xml,
        mock_get_google_events,
        mock_save_snapshots,
        mock_google_service,
        sample_xml_events,
        sample_google_events,
        snapshots_with_existing_data
    ):
        """Test that function handles the case when no changes are detected."""
        # Setup mocks
        mock_get_service.return_value = mock_google_service
        mock_parse_xml.return_value = sample_xml_events
        mock_get_google_events.return_value = sample_google_events
        mock_filter_events.return_value = sample_xml_events
        mock_load_snapshots.return_value = snapshots_with_existing_data
        
        # Mock detect_changes to return no changes
        mock_detect_changes.side_effect = [
            ([], [], []),  # Google changes (no changes)
            ([], [], [])   # XML changes (no changes)
        ]
        
        # Execute the function
        sync_calendar_with_diff()
        
        # Verify no API calls were made for creating/deleting events
        events_mock = mock_google_service.events.return_value
        events_mock.insert.assert_not_called()
        
        # Verify snapshots were still saved (for consistency)
        mock_save_snapshots.assert_called_once()

    @patch('src.main.save_snapshots')
    @patch('src.main.get_events_past_week_to_next_month')
    @patch('src.main.parse_local_xml')
    @patch('src.main.filter_events_by_time_range')
    @patch('src.main.load_snapshots')
    @patch('src.main.detect_changes')
    @patch('src.main.write_appointments_to_xml')
    @patch('src.main.rfc3339_to_dotnet_ticks')
    @patch('src.main.get_google_calendar_service')
    def test_skip_synced_events_to_avoid_duplicates(
        self,
        mock_get_service,
        mock_rfc3339_to_ticks,
        mock_write_xml,
        mock_detect_changes,
        mock_load_snapshots,
        mock_filter_events,
        mock_parse_xml,
        mock_get_google_events,
        mock_save_snapshots,
        mock_google_service,
        sample_xml_events,
        empty_snapshots
    ):
        """Test that events already synced from XML to Google are not duplicated."""
        # Setup mocks
        mock_get_service.return_value = mock_google_service
        mock_parse_xml.return_value = sample_xml_events
        mock_filter_events.return_value = sample_xml_events
        mock_load_snapshots.return_value = empty_snapshots
        mock_rfc3339_to_ticks.return_value = '637776648000000000'
        
        # Google event that was synced from XML (has special description)
        synced_google_event = {
            'id': 'google_synced',
            'summary': 'Previously Synced Event',
            'start': {'dateTime': '2024-01-20T10:00:00+00:00'},
            'end': {'dateTime': '2024-01-20T11:00:00+00:00'},
            'description': 'Synced from local XML - ID 1'
        }
        
        mock_get_google_events.return_value = [synced_google_event]
        
        # Mock detect_changes to return the synced event as a Google addition
        mock_detect_changes.side_effect = [
            ([synced_google_event], [], []),  # Google changes (addition of synced event)
            ([], [], [])  # XML changes (no changes)
        ]
        
        # Execute the function
        sync_calendar_with_diff()
        
        # Verify that the synced event was NOT added back to XML
        # The write_appointments_to_xml should not be called since no new events
        mock_write_xml.assert_not_called()
        
        # Verify snapshots were saved
        mock_save_snapshots.assert_called_once() 