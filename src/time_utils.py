from datetime import datetime, timezone, timedelta

def dotnet_ticks_to_rfc3339(ticks):
    """Convert .NET ticks to RFC3339 datetime string."""
    # .NET ticks are 100-nanosecond intervals since January 1, 0001 UTC
    # Unix epoch is January 1, 1970 UTC
    # There are 621355968000000000 ticks between 0001 and 1970
    unix_timestamp = (int(ticks) - 621355968000000000) / 10000000
    dt = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
    return dt.isoformat()

def rfc3339_to_dotnet_ticks(rfc3339_str):
    """Convert RFC3339 datetime string to .NET ticks."""
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

def filter_events_by_time_range(events, fetch_days_past=7, fetch_days_future=30):
    """Filter events to only include those within the specified time range."""
    now = datetime.now(timezone.utc)
    time_min = now - timedelta(days=fetch_days_past)
    time_max = now + timedelta(days=fetch_days_future)
    
    filtered_events = []
    for event in events:
        try:
            # Parse the event start time
            event_start = datetime.fromisoformat(event['start'].replace('Z', '+00:00'))
            if event_start.tzinfo is None:
                event_start = event_start.replace(tzinfo=timezone.utc)
            else:
                event_start = event_start.astimezone(timezone.utc)
            
            # Check if the event falls within our time range
            if time_min <= event_start <= time_max:
                filtered_events.append(event)
        except Exception as e:
            print(f"⚠️ Error parsing date for event '{event.get('description', 'Unknown')}': {e}")
            continue
    
    return filtered_events 