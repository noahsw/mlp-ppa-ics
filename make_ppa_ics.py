#!/usr/bin/env python3
"""
Generate ICS calendar for PPA tournament schedules.

Scrapes PPA tournament schedule pages and generates ICS calendar files.
Can work with both live URLs and local HTML files for testing.

Usage:
  python make_ppa_ics.py --tournament-url https://www.ppatour.com/tournament/2025/open-at-the-las-vegas-strip/#schedule
  python make_ppa_ics.py --schedule-url https://www.ppatour.com/schedule/
  python make_ppa_ics.py --tournament-file sample_ppa_schedule.html --tournament "Open at the Las Vegas Strip"
  python make_ppa_ics.py --schedule-file sample_ppa_tournaments.html
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

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    ZoneInfo = None


def fetch_html(url: str) -> Optional[str]:
    """Fetch HTML content from URL."""
    headers = {
        'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'Accept':
        'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }

    try:
        import gzip
        req = Request(url, headers=headers)
        with urlopen(req, timeout=30) as response:
            content = response.read()
            
            # Check if content is gzip compressed
            content_encoding = response.headers.get('Content-Encoding', '').lower()
            if content_encoding == 'gzip':
                try:
                    content = gzip.decompress(content)
                except Exception as e:
                    print(f"Failed to decompress gzip content: {e}", file=sys.stderr)
                    return None
            elif content_encoding == 'deflate':
                try:
                    import zlib
                    content = zlib.decompress(content)
                except Exception as e:
                    print(f"Failed to decompress deflate content: {e}", file=sys.stderr)
                    return None
            
            # Handle potential encoding issues
            try:
                return content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    return content.decode('latin-1')
                except UnicodeDecodeError:
                    return content.decode('utf-8', errors='replace')
                    
    except (URLError, HTTPError) as e:
        print(f"Error fetching URL {url}: {e}", file=sys.stderr)
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


def parse_tournament_schedule(html_content: str) -> List[Dict[str, Any]]:
    """Parse tournament page HTML and extract schedule events."""
    events = []

    # Look for the "how-to-watch" schedule section in the actual PPA website structure
    schedule_match = re.search(
        r'<section[^>]*id="how-to-watch"[^>]*>(.*?)</section>', html_content,
        re.DOTALL)
    if schedule_match:
        # Parse actual PPA website structure
        events = parse_ppa_website_structure(schedule_match.group(1))

    return events


def parse_schedule_content(html_content: str) -> List[Dict[str, Any]]:
    """Parse HTML content and extract schedule events."""
    events = []

    # Look for the "how-to-watch" schedule section in the actual PPA website structure
    schedule_match = re.search(
        r'<section[^>]*id="how-to-watch"[^>]*>(.*?)</section>', html_content,
        re.DOTALL)
    if schedule_match:
        # Parse actual PPA website structure
        events = parse_ppa_website_structure(schedule_match.group(1))

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
                broadcaster_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>',
                                              event_content)
                broadcaster = 'Unknown'
                if broadcaster_match:
                    href = broadcaster_match.group(1)
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
    # Parse "2:00 PM ET - 10:00 PM ET" format
    match = re.match(
        r'(\d{1,2}:\d{2}\s*(?:AM|PM))\s*ET\s*-\s*(\d{1,2}:\d{2}\s*(?:AM|PM))\s*ET',
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


def ics_escape(value: str) -> str:
    """Escape special characters for ICS format."""
    return (value.replace("\\", "\\\\").replace(";", "\\;").replace(
        ",", "\\,").replace("\n", "\\n"))


def fold_ical_line(line: str, limit: int = 75) -> List[str]:
    """Fold long ICS lines according to RFC 5545."""
    if len(line) <= limit:
        return [line]
    parts = [line[:limit]]
    s = line[limit:]
    while s:
        parts.append(" " + s[:limit])
        s = s[limit:]
    return parts


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

    description = "\\n".join(description_parts)

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
    folded_lines = []
    for line in event_lines:
        folded_lines.extend(fold_ical_line(line))

    return folded_lines


def write_ics_file(filename: str, events: List[Dict[str, Any]],
                   tournament_name: str):
    """Write events to ICS file."""
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PPA ICS Generator//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:PPA {tournament_name}",
        "X-WR-TIMEZONE:America/New_York",
    ]

    # Add events
    for event in events:
        event_lines = create_ics_event(event, tournament_name, dtstamp)
        if event_lines:
            lines.extend(event_lines)

    lines.append("END:VCALENDAR")

    # Write file with proper CRLF line endings
    ics_content = "\r\n".join(lines) + "\r\n"
    with open(filename, "wb") as f:
        f.write(ics_content.encode("utf-8"))

    print(f"Created {filename} with {len(events)} events")


def fetch_tournament_from_schedule(schedule_url: str, debug: bool = False) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Fetch tournament page from schedule page. Returns (html_content, tournament_url, tournament_name)"""
    if debug:
        print(f"Fetching schedule from: {schedule_url}")
    
    schedule_html = fetch_html(schedule_url)
    if not schedule_html:
        return None, None, None
    
    if debug:
        print(f"Schedule HTML length: {len(schedule_html)} characters")
        # Look for any tournament-related content
        tournament_mentions = re.findall(r'tournament[^>]*>', schedule_html, re.IGNORECASE)
        if tournament_mentions:
            print(f"Found {len(tournament_mentions)} tournament-related HTML elements")
            for i, mention in enumerate(tournament_mentions[:3]):  # Show first 3
                print(f"  {i+1}: {mention[:100]}...")
        else:
            print("No tournament-related HTML elements found")
    
    tournament_url = extract_first_tournament_url(schedule_html)
    if not tournament_url:
        if debug:
            print("No tournament URL found in schedule page")
            # Show some sample HTML to help debug
            print("Sample HTML content (first 500 chars):")
            print(schedule_html[:500])
        return None, None, None
    
    if debug:
        print(f"Found tournament URL: {tournament_url}")
    
    # Fetch the tournament page
    tournament_html = fetch_html(tournament_url)
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
    parser.add_argument("--tournament-url", help="PPA tournament page URL")
    parser.add_argument("--schedule-url", help="PPA schedule page URL (automatically finds first tournament)")
    parser.add_argument("--tournament-file", help="Local tournament HTML file to parse")
    parser.add_argument("--schedule-file", help="Local schedule HTML file to parse")
    parser.add_argument("--tournament",
                        default="Tournament",
                        help="Tournament name")
    parser.add_argument("--output",
                        default="ppa.ics",
                        help="Output ICS filename")
    parser.add_argument("--debug",
                        action="store_true",
                        help="Print debug information")

    args = parser.parse_args()

    # Default to schedule URL if no source is specified
    if not any([args.tournament_url, args.schedule_url, args.tournament_file, args.schedule_file]):
        args.schedule_url = "https://www.ppatour.com/schedule/"
        if args.debug:
            print("No source specified, defaulting to PPA schedule page")

    # Get HTML content
    if args.tournament_file:
        if args.debug:
            print(f"Reading tournament content from: {args.tournament_file}")
        try:
            with open(args.tournament_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except IOError as e:
            print(f"Error reading file {args.tournament_file}: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Parse tournament schedule from file
        events = parse_tournament_schedule(html_content)
        
    elif args.schedule_file:
        if args.debug:
            print(f"Reading schedule content from: {args.schedule_file}")
        try:
            with open(args.schedule_file, 'r', encoding='utf-8') as f:
                schedule_html = f.read()
        except IOError as e:
            print(f"Error reading file {args.schedule_file}: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Extract tournament URL from schedule file
        tournament_url = extract_first_tournament_url(schedule_html)
        if not tournament_url:
            print("No tournament URL found in schedule file", file=sys.stderr)
            sys.exit(1)
        
        if args.debug:
            print(f"Found tournament URL in file: {tournament_url}")
        
        # Fetch the tournament page
        html_content = fetch_html(tournament_url)
        if not html_content:
            print(f"Failed to fetch tournament page: {tournament_url}", file=sys.stderr)
            sys.exit(1)
        
        # Extract tournament name from URL if not provided
        if args.tournament == "Tournament":
            url_match = re.search(r'/tournament/\d+/([^/]+)/?', tournament_url)
            if url_match:
                args.tournament = url_match.group(1).replace('-', ' ').title()
        
        events = parse_tournament_schedule(html_content)
        
    elif args.schedule_url:
        # Fetch tournament from schedule page
        schedule_url = args.schedule_url
        html_content, tournament_url, tournament_name = fetch_tournament_from_schedule(schedule_url, args.debug)
        
        if not html_content:
            print("Failed to fetch tournament from schedule", file=sys.stderr)
            sys.exit(1)
        
        # Update tournament name if not provided
        if args.tournament == "Tournament":
            args.tournament = tournament_name
        
        events = parse_tournament_schedule(html_content)
        
    elif args.tournament_url:
        # Direct tournament URL
        tournament_url = args.tournament_url
        
        if args.debug:
            print(f"Fetching tournament from: {tournament_url}")
        
        html_content = fetch_html(tournament_url)
        if not html_content:
            print("Failed to fetch HTML content", file=sys.stderr)
            sys.exit(1)
        
        events = parse_tournament_schedule(html_content)
        
    else:
        print("Error: Must specify one of --tournament-url, --schedule-url, --tournament-file, or --schedule-file", file=sys.stderr)
        sys.exit(1)

    if args.debug:
        print(f"Found {len(events)} events:")
        for event in events:
            print(
                f"  {event['date']} - {event['court']} - {event['category']} - {event['time']} - {event.get('broadcaster', 'No broadcaster')}"
            )

    if not events:
        print("No events found in the HTML content", file=sys.stderr)
        sys.exit(1)

    # Write ICS file
    write_ics_file(args.output, events, args.tournament)


if __name__ == "__main__":
    main()
