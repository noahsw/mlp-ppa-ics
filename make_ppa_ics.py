#!/usr/bin/env python3
"""
Generate ICS calendar for PPA tournament schedules.

Scrapes PPA tournament schedule pages and generates ICS calendar files.
Can work with both live URLs and local HTML files for testing.

Usage:
  python make_ppa_ics.py --tournament-schedule-url https://www.ppatour.com/tournament/2025/open-at-the-las-vegas-strip/#schedule
  python make_ppa_ics.py --tour-schedule-url https://www.ppatour.com/schedule/
  python make_ppa_ics.py --tournament-schedule-file sample_ppa_schedule.html --tournament "Open at the Las Vegas Strip"
  python make_ppa_ics.py --tour-schedule-file sample_ppa_tournaments.html
"""

import os
import re
import sys
import argparse
import html
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from html.parser import HTMLParser
from ics_utils import ics_escape, fold_ical_line, get_ics_header, get_ics_footer, fold_event_lines, read_html_file

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    ZoneInfo = None


def fetch_html(url: str, debug: bool = False, max_retries: int = 3, timeout: int = 15) -> Optional[str]:
    """Fetch HTML content from URL with retries and better error handling."""
    if debug:
        print(f"Attempting to fetch: {url}")

    headers = {
        'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'Accept':
        'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }

    for attempt in range(1, max_retries + 1):
        try:
            import gzip
            import time

            if debug and attempt > 1:
                print(f"Retry attempt {attempt}/{max_retries}")

            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as response:
                if debug:
                    print(f"HTTP response status: {response.getcode()}")
                    print(f"Response headers: {dict(response.headers)}")

                content = response.read()
                if debug:
                    print(f"Raw content length: {len(content)} bytes")

                # Check if content is gzip compressed
                content_encoding = response.headers.get('Content-Encoding', '').lower()
                if content_encoding == 'gzip':
                    if debug:
                        print("Content is gzip compressed, decompressing...")
                    try:
                        content = gzip.decompress(content)
                        if debug:
                            print(f"Decompressed content length: {len(content)} bytes")
                    except Exception as e:
                        print(f"Failed to decompress gzip content: {e}", file=sys.stderr)
                        if debug:
                            print("First 100 bytes of raw content:", content[:100])
                        continue  # Try next attempt
                elif content_encoding == 'deflate':
                    if debug:
                        print("Content is deflate compressed, decompressing...")
                    try:
                        import zlib
                        content = zlib.decompress(content)
                        if debug:
                            print(f"Decompressed content length: {len(content)} bytes")
                    except Exception as e:
                        print(f"Failed to decompress deflate content: {e}", file=sys.stderr)
                        if debug:
                            print("First 100 bytes of raw content:", content[:100])
                        continue  # Try next attempt
                elif debug and content_encoding:
                    print(f"Unknown content encoding: {content_encoding}")

                # Handle potential encoding issues
                try:
                    decoded = content.decode('utf-8')
                    if debug:
                        print("Successfully decoded as UTF-8")
                        print(f"Final content length: {len(decoded)} characters")
                    return decoded
                except UnicodeDecodeError:
                    if debug:
                        print("UTF-8 decoding failed, trying latin-1...")
                    try:
                        decoded = content.decode('latin-1')
                        if debug:
                            print("Successfully decoded as latin-1")
                        return decoded
                    except UnicodeDecodeError:
                        if debug:
                            print("latin-1 decoding failed, using UTF-8 with error replacement...")
                        return content.decode('utf-8', errors='replace')

        except (URLError, HTTPError) as e:
            error_msg = f"Network error on attempt {attempt}/{max_retries}: {e}"
            if attempt == max_retries:
                print(f"Failed to fetch {url} after {max_retries} attempts: {e}", file=sys.stderr)
            elif debug:
                print(error_msg)

            if attempt < max_retries:
                wait_time = min(2 ** attempt, 10)  # Exponential backoff, max 10 seconds
                if debug:
                    print(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
                continue

        except Exception as e:
            error_msg = f"Unexpected error on attempt {attempt}/{max_retries}: {e}"
            if attempt == max_retries:
                print(f"Failed to fetch {url} after {max_retries} attempts due to unexpected error: {e}", file=sys.stderr)
                if debug:
                    import traceback
                    print("Full error traceback:", file=sys.stderr)
                    traceback.print_exc()
            elif debug:
                print(error_msg)

            if attempt < max_retries:
                wait_time = min(2 ** attempt, 10)  # Exponential backoff, max 10 seconds
                if debug:
                    print(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
                continue

    # All attempts failed
    return None


def extract_first_tournament_url(html_content: str) -> Optional[str]:
    """Extract the first tournament URL from the schedule page."""
    # Try multiple patterns to find tournament links
    patterns = [
        # Original pattern
        r'<a\s+href="(https://www\.ppatour\.com/tournament/[^"]+)"[^>]*class="tournament-schedule__item-link-wrap"',
        # Alternative pattern without class requirement
        r'<a\s+href="(https://www\.ppatour\.com/tournament/[^"]+)"',
        # Pattern for relative URLs
        r'<a\s+href="(/tournament/[^"]+)"[^>]*class="tournament-schedule__item-link-wrap"',
        # Simplified pattern
        r'href="(https://www\.ppatour\.com/tournament/[^"]+)"',
        # Pattern for any tournament link structure
        r'"(https://www\.ppatour\.com/tournament/\d+/[^"]+)"'
    ]

    for pattern in patterns:
        match = re.search(pattern, html_content)
        if match:
            url = match.group(1)
            # Convert relative URLs to absolute
            if url.startswith('/'):
                url = 'https://www.ppatour.com' + url
            return url

    return None


def parse_schedule_content(html_content: str, debug: bool = False) -> List[Dict[str, Any]]:
    """Parse HTML content and extract schedule events."""
    events = []

    # Look for the "how-to-watch" schedule section in the actual PPA website structure
    schedule_match = re.search(
        r'<section[^>]*id="how-to-watch"[^>]*>(.*?)</section>', html_content,
        re.DOTALL)
    if schedule_match:
        # Parse actual PPA website structure
        events = parse_ppa_website_structure(schedule_match.group(1))
    elif debug:
        print("Could not find the '#how-to-watch' section in the provided HTML.")

    if not events and debug:
        print("No events were parsed from the HTML content.")

    return events


def parse_ppa_website_structure(schedule_html: str) -> List[Dict[str, Any]]:
    """Parse the actual PPA website structure."""
    events = []

    # Extract day sections
    day_pattern = r'<div class="how-to-watch__schedule-day">(.*?)(?=<div class="how-to-watch__schedule-day">|$)'
    day_matches = re.finditer(day_pattern, schedule_html, re.DOTALL)

    for day_match in day_matches:
        day_content = day_match.group(1)

        # Extract date
        date_match = re.search(
            r'<h3[^>]*class="typo-heading--3"[^>]*>([^<]+)</h3>', day_content)
        if not date_match:
            continue

        date_text = html.unescape(date_match.group(1)).strip()
        parsed_date = parse_date_text(date_text)
        if not parsed_date:
            continue

        # Extract courts within this day
        court_pattern = r'<div class="how-to-watch__schedule-court">(.*?)(?=<div class="how-to-watch__schedule-court">|$)'
        court_matches = re.finditer(court_pattern, day_content, re.DOTALL)

        for court_match in court_matches:
            court_content = court_match.group(1)

            # Extract court name
            court_name_match = re.search(
                r'<h4[^>]*class="typo-heading--4"[^>]*>([^<]+)</h4>',
                court_content)
            if not court_name_match:
                continue

            court_name = html.unescape(court_name_match.group(1)).strip()

            # Extract events within this court
            event_pattern = r'<div class="how-to-watch__schedule-event">(.*?)(?=<div class="how-to-watch__schedule-event">|</div>\s*</div>\s*</div>)'
            event_matches = re.finditer(event_pattern, court_content,
                                        re.DOTALL)

            for event_match in event_matches:
                event_content = event_match.group(1)

                # Extract category and time from event title
                title_match = re.search(
                    r'<div class="how-to-watch__schedule-event-title">(.*?)</div>',
                    event_content, re.DOTALL)
                if not title_match:
                    continue

                title_content = title_match.group(1)

                # Extract category (span content)
                category_match = re.search(
                    r'<span[^>]*class="typo-heading--4"[^>]*>([^<]+)</span>',
                    title_content)
                if not category_match:
                    continue

                category = html.unescape(category_match.group(1)).strip()

                # Extract time (after the pipe)
                time_match = re.search(r'\|\s*<span>([^<]+)</span>',
                                       title_content)
                if not time_match:
                    continue

                time_text = html.unescape(time_match.group(1)).strip()

                # Extract broadcaster
                broadcaster = 'Unknown'
                broadcaster_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>',
                                              event_content)
                if broadcaster_match:
                    href = broadcaster_match.group(1).lower()
                    if 'pickleballtv.com' in href:
                        broadcaster = 'PickleballTV'
                    elif 'tennischannel.com' in href:
                        broadcaster = 'Tennis Channel'
                    elif 'foxsports.com/live/fs1' in href:
                        broadcaster = 'FS1'
                    elif 'foxsports.com/live/fs2' in href:
                        broadcaster = 'FS2'

                event = {
                    'date': parsed_date,
                    'court': court_name,
                    'category': category,
                    'time': time_text,
                    'broadcaster': broadcaster
                }
                events.append(event)

    return events


def parse_date_text(date_text: str) -> Optional[str]:
    """Parse date text into YYYY-MM-DD format."""
    match = re.search(r'(\w+),?\s+(\w+)\s+(\d+)', date_text)
    if match:
        weekday, month, day = match.groups()
        year = datetime.now().year
        try:
            month_num = datetime.strptime(month, '%B').month
            return f"{year}-{month_num:02d}-{int(day):02d}"
        except ValueError:
            pass
    return None


def parse_time_range(time_str: str,
                     event_date: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse time range string into UTC datetime strings."""
    # Parse "2:00 PM ET - 10:00 PM ET" format or "10:00 AM - 6:00 PM ET" format
    match = re.match(
        r'(\d{1,2}:\d{2}\s*(?:AM|PM))(?:\s*ET)?\s*-\s*(\d{1,2}:\d{2}\s*(?:AM|PM))\s*ET',
        time_str, re.IGNORECASE)
    if not match:
        return None, None

    start_time, end_time = match.groups()

    try:
        # Parse the date
        event_dt = datetime.strptime(event_date, '%Y-%m-%d')

        # Parse start time
        start_dt = datetime.strptime(f"{event_date} {start_time}",
                                     '%Y-%m-%d %I:%M %p')

        # Parse end time
        end_dt = datetime.strptime(f"{event_date} {end_time}",
                                   '%Y-%m-%d %I:%M %p')

        # Handle midnight crossover (end time next day)
        if end_dt < start_dt:
            end_dt += timedelta(days=1)

        # Convert to Eastern Time, then to UTC
        if ZoneInfo:
            eastern = ZoneInfo('America/New_York')
            start_dt = start_dt.replace(tzinfo=eastern)
            end_dt = end_dt.replace(tzinfo=eastern)

            # Convert to UTC
            start_utc = start_dt.astimezone(timezone.utc)
            end_utc = end_dt.astimezone(timezone.utc)
        else:
            # Fallback: assume EST (UTC-5) or EDT (UTC-4) based on date
            # This is a simplified approach
            est_offset = timedelta(hours=5)  # Assume EST for now
            start_utc = start_dt.replace(tzinfo=timezone.utc) + est_offset
            end_utc = end_dt.replace(tzinfo=timezone.utc) + est_offset

        return start_utc.strftime('%Y-%m-%dT%H:%M:%SZ'), end_utc.strftime(
            '%Y-%m-%dT%H:%M:%SZ')

    except ValueError as e:
        print(f"Error parsing time range '{time_str}': {e}", file=sys.stderr)
        return None, None


def create_ics_event(event: Dict[str, Any], tournament_name: str,
                     dtstamp: str) -> List[str]:
    """Create ICS event lines for a PPA event."""
    start_time, end_time = parse_time_range(event['time'], event['date'])
    if not start_time or not end_time:
        return []

    # Create event title
    category = event.get('category', 'Tournament')
    court = event.get('court', 'Court')
    broadcaster = event.get('broadcaster', '')

    if broadcaster:
        summary = f"PPA {category} ({court}) - {broadcaster}"
    else:
        summary = f"PPA {category} ({court})"

    # Create description
    description_parts = [f"Tournament: {tournament_name}"]
    if category:
        description_parts.append(f"Category: {category}")
    if court:
        description_parts.append(f"Court: {court}")
    if broadcaster:
        description_parts.append(f"Broadcaster: {broadcaster}")

    description = "\n".join(description_parts)

    # Create unique ID
    date_str = event['date'].replace('-', '')
    court_slug = re.sub(r'[^a-zA-Z0-9]', '', court.lower())
    category_slug = re.sub(r'[^a-zA-Z0-9]', '', category.lower())
    uid = f"ppa-{date_str}-{court_slug}-{category_slug}@ppatour.com"

    # Format times for ICS
    start_ics = start_time.replace('-', '').replace(':', '').replace('Z', 'Z')
    end_ics = end_time.replace('-', '').replace(':', '').replace('Z', 'Z')

    event_lines = [
        "BEGIN:VEVENT",
        f"UID:{ics_escape(uid)}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{start_ics}",
        f"DTEND:{end_ics}",
        f"SUMMARY:{ics_escape(summary)}",
        f"DESCRIPTION:{ics_escape(description)}",
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
        "END:VEVENT",
    ]

    # Fold long lines
    return fold_event_lines(event_lines)


def filter_championship_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter events to include only those categorized as Championships."""
    championship_events = []
    for event in events:
        category = event.get("category", "").lower()
        # Match various championship-related categories
        if any(keyword in category for keyword in ["championship", "final", "medal"]):
            championship_events.append(event)
    return championship_events


def filter_singles_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter events to include only Singles events."""
    return [event for event in events if "singles" in event.get("category", "").lower()]


def filter_gender_doubles_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter events to include only Men's/Women's Doubles events."""
    gender_doubles_events = []
    for event in events:
        category = event.get("category", "").lower()
        # Match various gender doubles patterns
        if any(keyword in category for keyword in ["men's", "women's", "men's/women's", "gender"]):
            gender_doubles_events.append(event)
    return gender_doubles_events


def filter_mixed_doubles_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter events to include only Mixed Doubles events."""
    return [event for event in events if "mixed" in event.get("category", "").lower()]


def filter_by_broadcaster(events: List[Dict[str, Any]], broadcaster: str) -> List[Dict[str, Any]]:
    """Filter events by broadcaster."""
    return [event for event in events if event.get("broadcaster", "").lower() == broadcaster.lower()]


def filter_by_court(events: List[Dict[str, Any]], court: str) -> List[Dict[str, Any]]:
    """Filter events by court name."""
    return [event for event in events if court.lower() in event.get("court", "").lower()]


def write_ics_file(filename: str, events: List[Dict[str, Any]],
                   tournament_name: str, calendar_title: str = "PPA Tour"):
    """Write events to ICS file."""
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = []
    lines.extend(get_ics_header(calendar_title, "America/New_York"))

    # Add events
    for event in events:
        event_lines = create_ics_event(event, tournament_name, dtstamp)
        if event_lines:
            lines.extend(event_lines)

    lines.extend(get_ics_footer())

    # Write file with proper CRLF line endings
    ics_content = "\r\n".join(lines) + "\r\n"
    with open(filename, "wb") as f:
        f.write(ics_content.encode("utf-8"))

    if len(events) == 0:
        print(f"Created {filename} with 0 events (empty calendar)")
    else:
        print(f"Created {filename} with {len(events)} events")


def write_all_ics_files(base_filename: str, all_events: List[Dict[str, Any]], tournament_name: str, debug: bool = False):
    """Write all specialized ICS files based on different filters."""
    base, ext = os.path.splitext(base_filename)

    # Define all the filters and their corresponding filenames and calendar titles
    filters = [
        ("", all_events, "PPA Tour"),  # Main file with all events
        ("-championships", filter_championship_events(all_events), "PPA Tour - Championships"),
        ("-singles", filter_singles_events(all_events), "PPA Tour - Singles"),
        ("-gender-doubles", filter_gender_doubles_events(all_events), "PPA Tour - Men's/Women's Doubles"),
        ("-mixed-doubles", filter_mixed_doubles_events(all_events), "PPA Tour - Mixed Doubles"),
        ("-pickleballtv", filter_by_broadcaster(all_events, "PickleballTV"), "PPA Tour - PickleballTV"),
        ("-tennis-channel", filter_by_broadcaster(all_events, "Tennis Channel"), "PPA Tour - Tennis Channel"),
        ("-fs1", filter_by_broadcaster(all_events, "FS1"), "PPA Tour - FS1"),
        ("-fs2", filter_by_broadcaster(all_events, "FS2"), "PPA Tour - FS2"),
        ("-championship-court", filter_by_court(all_events, "Championship Court"), "PPA Tour - Championship Court"),
        ("-grandstand-court", filter_by_court(all_events, "Grandstand Court"), "PPA Tour - Grandstand Court"),
    ]

    files_created = 0
    for suffix, filtered_events, calendar_title in filters:
        if filtered_events:
            filename = f"{base}{suffix}{ext}"
            write_ics_file(filename, filtered_events, tournament_name, calendar_title)
            files_created += 1
        elif debug:
            print(f"No events found for {calendar_title}, skipping {base}{suffix}{ext}")

    if debug:
        print(f"Created {files_created} ICS files from {len(all_events)} total events")


def fetch_tournament_from_schedule(schedule_url: str, debug: bool = False) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Fetch tournament page from schedule page. Returns (html_content, tournament_url, tournament_name)"""
    if debug:
        print(f"Fetching schedule from: {schedule_url}")

    schedule_html = fetch_html(schedule_url, debug=debug)
    if not schedule_html:
        print(f"Unable to fetch schedule page from {schedule_url}. This may be due to:", file=sys.stderr)
        print("  - Network connectivity issues", file=sys.stderr)
        print("  - Website blocking automated requests", file=sys.stderr)
        print("  - Server timeouts or temporary unavailability", file=sys.stderr)
        print("  - Try again later or use a local HTML file with --tour-schedule-file", file=sys.stderr)
        return None, None, None

    if debug:
        print(f"Schedule HTML fetched successfully: {len(schedule_html)} characters")

        # Check if we got valid HTML
        if schedule_html.startswith('<!DOCTYPE') or schedule_html.startswith('<html'):
            print("✓ HTML appears to be valid (starts with DOCTYPE or html tag)")
        else:
            print("⚠ HTML may be invalid or corrupted")
            print("First 200 characters:", repr(schedule_html[:200]))

        # Look for any tournament-related content with multiple patterns
        patterns_to_check = [
            (r'tournament[^>]*>', 'tournament mentions'),
            (r'href="[^"]*tournament[^"]*"', 'tournament links'),
            (r'ppatour\.com/tournament', 'PPA tournament URLs'),
            (r'class="[^"]*tournament[^"]*"', 'tournament CSS classes'),
            (r'<a[^>]*href="[^"]*tournament[^"]*"[^>]*>', 'tournament link tags')
        ]

        for pattern, description in patterns_to_check:
            matches = re.findall(pattern, schedule_html, re.IGNORECASE)
            if matches:
                print(f"Found {len(matches)} {description}")
                for i, match in enumerate(matches[:2]):  # Show first 2
                    print(f"  {i+1}: {match[:100]}...")
            else:
                print(f"No {description} found")

    tournament_url = extract_first_tournament_url(schedule_html)
    if not tournament_url:
        if debug:
            print("ERROR: No tournament URL found in schedule page")
            print("\nDebugging URL extraction:")
            print("Trying all URL extraction patterns...")

            # Test each pattern individually for debugging
            patterns = [
                r'<a\s+href="(https://www\.ppatour\.com/tournament/[^"]+)"[^>]*class="tournament-schedule__item-link-wrap"',
                r'<a\s+href="(https://www\.ppatour\.com/tournament/[^"]+)"',
                r'<a\s+href="(/tournament/[^"]+)"[^>]*class="tournament-schedule__item-link-wrap"',
                r'href="(https://www\.ppatour\.com/tournament/[^"]+)"',
                r'"(https://www\.ppatour\.com/tournament/\d+/[^"]+)"'
            ]

            for i, pattern in enumerate(patterns):
                matches = re.findall(pattern, schedule_html)
                if matches:
                    print(f"  Pattern {i+1}: Found {len(matches)} matches")
                    for j, match in enumerate(matches[:2]):
                        print(f"    {j+1}: {match}")
                else:
                    print(f"  Pattern {i+1}: No matches")

            # Show sample HTML around any tournament mentions
            tournament_indices = [m.start() for m in re.finditer(r'tournament', schedule_html, re.IGNORECASE)]
            if tournament_indices:
                print(f"\nSample HTML around tournament mentions (showing first 3 of {len(tournament_indices)}):")
                for i, idx in enumerate(tournament_indices[:3]):
                    start = max(0, idx - 100)
                    end = min(len(schedule_html), idx + 200)
                    sample = schedule_html[start:end]
                    print(f"  Context {i+1}: ...{sample}...")
            else:
                print("\nNo 'tournament' text found anywhere in HTML")
                print("Sample HTML content (first 1000 chars):")
                print(schedule_html[:1000])

        return None, None, None

    if debug:
        print(f"Found tournament URL: {tournament_url}")

    # Fetch the tournament page
    tournament_html = fetch_html(tournament_url, debug=debug)
    if not tournament_html:
        if debug:
            print(f"Failed to fetch tournament page: {tournament_url}")
        return None, None, None

    # Extract tournament name from URL
    tournament_name = "Tournament"
    url_match = re.search(r'/tournament/\d+/([^/]+)/?', tournament_url)
    if url_match:
        tournament_name = url_match.group(1).replace('-', ' ').title()
        if debug:
            print(f"Extracted tournament name: {tournament_name}")

    return tournament_html, tournament_url, tournament_name


def main():
    parser = argparse.ArgumentParser(
        description="Generate ICS calendar for PPA tournament schedules")
    parser.add_argument("--tournament-schedule-url", help="PPA tournament page URL")
    parser.add_argument("--tour-schedule-url", help="PPA schedule page URL (automatically finds first tournament)")
    parser.add_argument("--tournament-schedule-file", help="Local tournament schedule HTML file (specific tournament's how-to-watch page)")
    parser.add_argument("--tour-schedule-file", help="Local tour schedule HTML file (main tournaments listing page)")
    parser.add_argument("--tournament",
                        default="Tournament",
                        help="Tournament name")
    parser.add_argument("--output",
                        default="ppa.ics",
                        help="Output ICS filename")
    parser.add_argument("--championships-only",
                        action="store_true",
                        help="Filter to only championship events (creates ppa-championships.ics by default)")
    parser.add_argument("--pickleballtv", action='store_true',
                        help='Create ICS file with only PickleballTV events')
    parser.add_argument('--tennis-channel', action='store_true',
                        help='Create ICS file with only Tennis Channel events')
    parser.add_argument('--fs1', action='store_true',
                        help='Create ICS file with only FS1 events')
    parser.add_argument('--fs2', action='store_true',
                        help='Create ICS file with only FS2 events')
    parser.add_argument("--debug",
                        action="store_true",
                        help="Print debug information")

    args = parser.parse_args()

    # Default to tour schedule URL if no source is specified
    if not any([args.tournament_schedule_url, args.tour_schedule_url, args.tournament_schedule_file, args.tour_schedule_file]):
        args.tour_schedule_url = "https://www.ppatour.com/schedule/"
        if args.debug:
            print("No source specified, defaulting to PPA schedule page")

    # Get HTML content
    if args.tournament_schedule_file:
        if args.debug:
            print(f"Reading tournament content from: {args.tournament_schedule_file}")
        try:
            html_content = read_html_file(args.tournament_schedule_file, debug=args.debug)
        except IOError:
            sys.exit(1)

        # Parse tournament schedule from file
        events = parse_schedule_content(html_content, args.debug)

    elif args.tour_schedule_file:
        if args.debug:
            print(f"Reading schedule content from: {args.tour_schedule_file}")
        try:
            schedule_html = read_html_file(args.tour_schedule_file, debug=args.debug)
        except IOError:
            sys.exit(1)

        # Extract tournament URL from schedule file
        tournament_url = extract_first_tournament_url(schedule_html)
        if not tournament_url:
            print("No tournament URL found in schedule file", file=sys.stderr)
            sys.exit(1)

        if args.debug:
            print(f"Found tournament URL in file: {tournament_url}")

        # Fetch the tournament page
        html_content = fetch_html(tournament_url, debug=args.debug)
        if not html_content:
            print(f"Failed to fetch tournament page: {tournament_url}", file=sys.stderr)
            sys.exit(1)

        # Extract tournament name from URL if not provided
        if args.tournament == "Tournament":
            url_match = re.search(r'/tournament/\d+/([^/]+)/?', tournament_url)
            if url_match:
                args.tournament = url_match.group(1).replace('-', ' ').title()

        events = parse_schedule_content(html_content, args.debug)

    elif args.tour_schedule_url:
        # Fetch tournament from schedule page
        schedule_url = args.tour_schedule_url
        html_content, tournament_url, tournament_name = fetch_tournament_from_schedule(schedule_url, args.debug)

        if not html_content:
            print("\nFailed to fetch tournament schedule from PPA website.", file=sys.stderr)
            print("Alternative options:", file=sys.stderr)
            print("  1. Try again later (the website may be temporarily unavailable)", file=sys.stderr)
            print("  2. Use a local HTML file: --tour-schedule-file sample_ppa_tour_schedule.html", file=sys.stderr)
            print("  3. Use a specific tournament URL: --tournament-schedule-url [TOURNAMENT_URL]", file=sys.stderr)
            sys.exit(1)

        # Update tournament name if not provided
        if args.tournament == "Tournament":
            args.tournament = tournament_name

        events = parse_schedule_content(html_content, args.debug)

    elif args.tournament_schedule_url:
        # Direct tournament URL
        tournament_url = args.tournament_schedule_url

        if args.debug:
            print(f"Fetching tournament from: {tournament_url}")

        html_content = fetch_html(tournament_url, debug=args.debug)
        if not html_content:
            print(f"\nFailed to fetch tournament page from {tournament_url}", file=sys.stderr)
            print("This may be due to:", file=sys.stderr)
            print("  - Invalid or outdated tournament URL", file=sys.stderr)
            print("  - Network connectivity issues", file=sys.stderr)
            print("  - Website blocking automated requests", file=sys.stderr)
            print("  - Try using a local HTML file: --tournament-schedule-file [FILE]", file=sys.stderr)
            sys.exit(1)

        events = parse_schedule_content(html_content, args.debug)

    else:
        print("Error: Must specify one of --tournament-schedule-url, --tour-schedule-url, --tournament-schedule-file, or --tour-schedule-file", file=sys.stderr)
        sys.exit(1)

    if args.debug:
        print(f"Found {len(events)} events:")
        for event in events:
            print(
                f"  {event['date']} - {event['court']} - {event['category']} - {event['time']} - {event.get('broadcaster', 'No broadcaster')}"
            )

    if not events:
        print("No events found in the HTML content - creating empty ICS file", file=sys.stderr)
        # Create empty ICS file instead of exiting with error
        write_ics_file(args.output, [], args.tournament, "PPA Tour")
        return

    # Handle championships-only flag for backward compatibility
    if args.championships_only:
        championship_events = filter_championship_events(events)
        if args.debug:
            print(f"Filtering to {len(championship_events)} championship events out of {len(events)} total events")
        if not championship_events:
            print("No championship events found in the tournament schedule - creating empty ICS file", file=sys.stderr)
            # Create empty championships ICS file instead of exiting with error
            base, ext = os.path.splitext(args.output)
            championships_filename = f"{base}-championships{ext}"
            write_ics_file(championships_filename, [], args.tournament, "PPA Tour - Championships")
            return
        # Write only championships file with modified filename
        base, ext = os.path.splitext(args.output)
        championships_filename = f"{base}-championships{ext}"
        write_ics_file(championships_filename, championship_events, args.tournament, "PPA Tour - Championships")
    else:
        # Generate broadcaster-specific files if any broadcaster flags are set
        broadcasters = ['PickleballTV', 'Tennis Channel', 'FS1', 'FS2']
        broadcaster_flags = [args.pickleballtv, args.tennis_channel, args.fs1, args.fs2]

        broadcaster_filenames = {
            'PickleballTV': 'pickleballtv',
            'Tennis Channel': 'tennis-channel',
            'FS1': 'fs1',
            'FS2': 'fs2'
        }

        for i, broadcaster in enumerate(broadcasters):
            if broadcaster_flags[i]:
                filtered_events = filter_by_broadcaster(events, broadcaster)
                if filtered_events:
                    filename_suffix = broadcaster_filenames.get(broadcaster, broadcaster.lower())
                    output_filename = f"{os.path.splitext(args.output)[0]}-{filename_suffix}.ics"
                    calendar_title = f"PPA Tour - {broadcaster}"
                    write_ics_file(output_filename, filtered_events, args.tournament, calendar_title)
                elif args.debug:
                    print(f"No events found for {broadcaster}, skipping {output_filename}")

        # If no specific broadcaster or championship flags are set, write all files
        if not any(broadcaster_flags) and not args.championships_only:
            if args.debug:
                print(f"Creating all specialized calendar files from {len(events)} total events")
            write_all_ics_files(args.output, events, args.tournament, args.debug)
        elif args.championships_only:
            # Championships-only was handled above, but ensure write_all_ics_files isn't called unnecessarily
            pass
        elif any(broadcaster_flags):
             # If only broadcaster flags were set, we've already handled those.
             # We might still want to create the main ppa.ics file if desired,
             # but the current logic prioritizes specific files.
             # For now, we'll assume that if specific flags are set, those are the desired outputs.
             pass



if __name__ == "__main__":
    main()