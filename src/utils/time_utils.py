"""
Time Utility Functions

Provides time-based utilities for risk assessment:
- UTC timestamp management
- Time range calculations
- Schedule-aware timing
- Monitoring cycle tracking
"""

from datetime import datetime, timedelta, timezone
from typing import Tuple


def get_utc_now() -> datetime:
    """
    Get current UTC timestamp with timezone info.

    Returns:
        Current datetime in UTC timezone
    """
    return datetime.now(timezone.utc)


def get_utc_timestamp_str() -> str:
    """
    Get current UTC timestamp as ISO format string.

    Returns:
        ISO format timestamp string (e.g., "2026-07-20T14:30:00Z")
    """
    return get_utc_now().isoformat().replace('+00:00', 'Z')


def hours_ago(hours: int) -> datetime:
    """
    Get a datetime that is N hours in the past.

    Args:
        hours: Number of hours ago (positive integer)

    Returns:
        Datetime object for N hours ago in UTC
    """
    return get_utc_now() - timedelta(hours=hours)


def minutes_ago(minutes: int) -> datetime:
    """
    Get a datetime that is N minutes in the past.

    Args:
        minutes: Number of minutes ago (positive integer)

    Returns:
        Datetime object for N minutes ago in UTC
    """
    return get_utc_now() - timedelta(minutes=minutes)


def days_ago(days: int) -> datetime:
    """
    Get a datetime that is N days in the past.

    Args:
        days: Number of days ago (positive integer)

    Returns:
        Datetime object for N days ago in UTC
    """
    return get_utc_now() - timedelta(days=days)


def seconds_ago(seconds: int) -> datetime:
    """
    Get a datetime that is N seconds in the past.

    Args:
        seconds: Number of seconds ago (positive integer)

    Returns:
        Datetime object for N seconds ago in UTC
    """
    return get_utc_now() - timedelta(seconds=seconds)


def time_since(timestamp: datetime) -> float:
    """
    Calculate seconds elapsed since a given timestamp.

    Args:
        timestamp: Past datetime to compare against

    Returns:
        Seconds elapsed (float)
    """
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    elapsed = get_utc_now() - timestamp
    return elapsed.total_seconds()


def is_older_than(timestamp: datetime, hours: int) -> bool:
    """
    Check if a timestamp is older than N hours.

    Args:
        timestamp: Datetime to check
        hours: Number of hours threshold

    Returns:
        True if timestamp is older than N hours, False otherwise
    """
    cutoff = hours_ago(hours)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp < cutoff


def is_within_hours(timestamp: datetime, hours: int) -> bool:
    """
    Check if a timestamp is within the last N hours.

    Args:
        timestamp: Datetime to check
        hours: Number of hours threshold

    Returns:
        True if timestamp is within last N hours, False otherwise
    """
    return not is_older_than(timestamp, hours)


def get_monitoring_cycle_time(interval_minutes: int = 5) -> datetime:
    """
    Get the next scheduled monitoring cycle time.

    Args:
        interval_minutes: Monitoring interval in minutes (default: 5)

    Returns:
        Rounded datetime to next monitoring cycle
    """
    now = get_utc_now()
    minutes_since_hour = now.minute
    minute_interval = minutes_since_hour // interval_minutes * interval_minutes

    return now.replace(minute=minute_interval, second=0, microsecond=0)


def get_last_cycle_time(interval_minutes: int = 5) -> datetime:
    """
    Get the previous completed monitoring cycle time.

    Args:
        interval_minutes: Monitoring interval in minutes (default: 5)

    Returns:
        Rounded datetime to last completed monitoring cycle
    """
    cycle_time = get_monitoring_cycle_time(interval_minutes)
    return cycle_time - timedelta(minutes=interval_minutes)


def next_cycle_in(interval_minutes: int = 5) -> float:
    """
    Get seconds until next monitoring cycle.

    Args:
        interval_minutes: Monitoring interval in minutes (default: 5)

    Returns:
        Seconds until next cycle (float)
    """
    now = get_utc_now()
    next_cycle = get_monitoring_cycle_time(interval_minutes) + timedelta(minutes=interval_minutes)
    return (next_cycle - now).total_seconds()


def format_timestamp(timestamp: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format a datetime object to string.

    Args:
        timestamp: Datetime to format
        format_str: Format string (default: "YYYY-MM-DD HH:MM:SS")

    Returns:
        Formatted timestamp string
    """
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.strftime(format_str)


def parse_iso_timestamp(timestamp_str: str) -> datetime:
    """
    Parse ISO format timestamp string to datetime.

    Args:
        timestamp_str: ISO format string (e.g., "2026-07-20T14:30:00Z")

    Returns:
        Datetime object in UTC

    Raises:
        ValueError: If string is not valid ISO format
    """
    try:
        # Handle both formats: with and without 'Z'
        ts_str = timestamp_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(ts_str)

        # Ensure UTC timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
    except ValueError as e:
        raise ValueError(f"Invalid ISO timestamp format: {timestamp_str}") from e


def get_date_range(days: int = 7) -> Tuple[datetime, datetime]:
    """
    Get a date range tuple (start, end) for the last N days.

    Args:
        days: Number of days to go back (default: 7)

    Returns:
        Tuple of (start_datetime, end_datetime) in UTC
    """
    end = get_utc_now()
    start = days_ago(days)
    return (start, end)


def is_business_hours(timestamp: datetime = None) -> bool:
    """
    Check if timestamp is during business hours (9 AM - 5 PM UTC).

    Args:
        timestamp: Datetime to check (default: now)

    Returns:
        True if during business hours, False otherwise
    """
    if timestamp is None:
        timestamp = get_utc_now()

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    hour = timestamp.hour
    # Business hours: 9 AM to 5 PM (9-17)
    return 9 <= hour < 17


if __name__ == "__main__":
    # Test functions
    print("=" * 60)
    print("Time Utilities Test")
    print("=" * 60)

    # Test 1: Current UTC time
    print("\n1. Current UTC Time")
    print("-" * 60)
    now = get_utc_now()
    print(f"UTC Now: {now}")
    print(f"ISO Format: {get_utc_timestamp_str()}")

    # Test 2: Time ranges
    print("\n2. Time Ranges")
    print("-" * 60)
    print(f"1 hour ago: {hours_ago(1)}")
    print(f"1 day ago:  {days_ago(1)}")
    print(f"1 week ago: {days_ago(7)}")

    # Test 3: Time since
    print("\n3. Time Since")
    print("-" * 60)
    past = minutes_ago(30)
    elapsed = time_since(past)
    print(f"Timestamp: {past}")
    print(f"Elapsed: {elapsed:.1f} seconds (~30 min)")

    # Test 4: Freshness checks
    print("\n4. Freshness Checks")
    print("-" * 60)
    recent = minutes_ago(10)
    old = days_ago(3)

    print(f"10 min old, within 1 hour: {is_within_hours(recent, 1)}")
    print(f"3 days old, within 1 hour: {is_within_hours(old, 1)}")
    print(f"3 days old, older than 1 day: {is_older_than(old, 24)}")

    # Test 5: Monitoring cycles
    print("\n5. Monitoring Cycles (5-minute interval)")
    print("-" * 60)
    current_cycle = get_monitoring_cycle_time(5)
    last_cycle = get_last_cycle_time(5)
    next_in = next_cycle_in(5)

    print(f"Current cycle: {current_cycle}")
    print(f"Last cycle:    {last_cycle}")
    print(f"Next cycle in: {next_in:.1f} seconds")

    # Test 6: Timestamp formatting
    print("\n6. Timestamp Formatting")
    print("-" * 60)
    ts = get_utc_now()
    print(f"Default format: {format_timestamp(ts)}")
    print(f"Date only:      {format_timestamp(ts, '%Y-%m-%d')}")
    print(f"ISO format:     {format_timestamp(ts, '%Y-%m-%dT%H:%M:%SZ')}")

    # Test 7: Business hours
    print("\n7. Business Hours Check")
    print("-" * 60)
    print(f"Is now business hours (9-5 UTC): {is_business_hours()}")

    # Test 8: Date ranges
    print("\n8. Date Ranges")
    print("-" * 60)
    start, end = get_date_range(7)
    print(f"Last 7 days:")
    print(f"  Start: {start}")
    print(f"  End:   {end}")

    print("\n" + "=" * 60)
    print("All tests complete!")
    print("=" * 60)
