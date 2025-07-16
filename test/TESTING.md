# Testing Documentation for sync_calendar_with_diff

## Overview

This document describes the comprehensive pytest test suite implemented for the `sync_calendar_with_diff` function in `src/main.py`.

## Test Coverage

The test suite covers **6 key scenarios** that ensure the calendar synchronization function works correctly:

### 1. XML Additions → Google Calendar (`test_xml_additions_sync_to_google`)
- **Purpose**: Verifies that new events added to the local XML calendar are properly synced to Google Calendar
- **Test Logic**: Mocks a new XML event and verifies it gets created in Google Calendar with correct parameters
- **Assertions**: Checks that Google Calendar API is called with the right event data

### 2. Google Additions → XML (`test_google_additions_sync_to_xml`)
- **Purpose**: Verifies that new events added to Google Calendar are properly synced to the local XML calendar
- **Test Logic**: Mocks a new Google Calendar event and verifies it gets added to XML with proper format conversion
- **Assertions**: Checks that XML is updated with the new event and time conversion occurs

### 3. XML Deletions → Google Calendar (`test_xml_deletions_sync_to_google`)
- **Purpose**: Verifies that events deleted from local XML calendar are properly removed from Google Calendar
- **Test Logic**: Simulates deletion of an XML event and checks that corresponding Google event is deleted
- **Assertions**: Verifies that the delete_google_events function is called with the correct event

### 4. Google Deletions → XML (`test_google_deletions_sync_to_xml`)
- **Purpose**: Verifies that events deleted from Google Calendar are properly removed from local XML calendar
- **Test Logic**: Simulates deletion of a Google event and checks that corresponding XML event is deleted
- **Assertions**: Verifies that the delete_xml_events function is called with correct parameters

### 5. No Changes Detected (`test_no_changes_detected`)
- **Purpose**: Ensures the function handles scenarios where no changes are detected gracefully
- **Test Logic**: Mocks no changes in either calendar and verifies no API calls are made
- **Assertions**: Confirms no insert operations occur when no changes are detected

### 6. Skip Synced Events (`test_skip_synced_events_to_avoid_duplicates`)
- **Purpose**: Prevents infinite sync loops by skipping events that were already synced from XML to Google
- **Test Logic**: Tests that events with "Synced from local XML" description are not re-synced back to XML
- **Assertions**: Verifies that already-synced events are not duplicated

## Test Architecture

### Best Practices Implemented

1. **Comprehensive Mocking**: All external dependencies are properly mocked:
   - Google Calendar API service
   - XML file operations
   - Snapshot management
   - Event detection and filtering

2. **Proper Fixtures**: Reusable test data fixtures for:
   - Sample XML events
   - Sample Google Calendar events
   - Empty snapshots (for initial sync)
   - Snapshots with existing data (for change detection)

3. **Isolated Testing**: Each test is completely isolated and doesn't depend on external resources

4. **Clear Test Structure**: Each test follows the Arrange-Act-Assert pattern

5. **Descriptive Test Names**: Test names clearly describe what scenario is being tested

## Files Created/Modified

- `test/test_sync_calendar.py`: Main test file with all test cases
- `test/conftest.py`: Pytest configuration with shared fixtures and settings
- `requirements.txt`: Added pytest and pytest-mock dependencies
- `test/TESTING.md`: This documentation file

## Running the Tests

### Run all tests:
```bash
python -m pytest test/ -v
```

### Run only unit tests:
```bash
python -m pytest test/ -v -m unit
```

### Run with quiet output:
```bash
python -m pytest test/
```

## Test Results

All 6 tests pass successfully, providing confidence that the `sync_calendar_with_diff` function:
- ✅ Correctly syncs additions in both directions (XML ↔ Google)
- ✅ Correctly syncs deletions in both directions (XML ↔ Google)
- ✅ Handles no-change scenarios gracefully
- ✅ Prevents duplicate syncing of already-synced events
- ✅ Maintains proper error handling and state management

## Mock Strategy

The tests use a sophisticated mocking strategy that:
- Isolates the function under test from all external dependencies
- Provides predictable behavior for all external calls
- Allows verification of function interactions with external systems
- Maintains test reliability and speed

This comprehensive test suite ensures the calendar synchronization functionality is robust and reliable. 