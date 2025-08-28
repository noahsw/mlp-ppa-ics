
#!/usr/bin/env python3
"""
Generate ICS calendar for PPA tournament schedules.

Scrapes PPA tournament schedule pages and generates ICS calendar files.
Can work with both live URLs and local HTML files for testing.

Usage:
  python make_ppa_ics.py --url https://www.ppatour.com/tournament/2025/open-at-the-las-vegas-strip/#schedule
  python make_ppa_ics.py --file ppa_schedule_example.html --tournament "Open at the Las Vegas Strip"
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

class PPAScheduleParser(HTMLParser):
    """HTML parser to extract PPA tournament schedule information."""
    
    def __init__(self):
        super().__init__()
        self.events = []
        self.current_date = None
        self.current_court = None
        self.current_event = {}
        self.in_date_header = False
        self.in_court_header = False
        self.in_category = False
        self.in_time = False
        self.in_broadcaster = False
        self.text_buffer = ""
        
    def handle_starttag(self, tag, attrs):
        # Look for date headers (h2, h3, or div with date-like text)
        if tag in ['h2', 'h3']:
            self.in_date_header = True
            self.text_buffer = ""
        elif tag == 'div':
            class_attr = dict(attrs).get('class', '')
            if 'court' in class_attr.lower():
                self.in_court_header = True
                self.text_buffer = ""
        elif tag == 'span':
            class_attr = dict(attrs).get('class', '')
            if 'category' in class_attr:
                self.in_category = True
                self.text_buffer = ""
            elif 'time' in class_attr:
                self.in_time = True
                self.text_buffer = ""
            elif 'broadcaster' in class_attr:
                self.in_broadcaster = True
                self.text_buffer = ""
                
    def handle_endtag(self, tag):
        if tag in ['h2', 'h3'] and self.in_date_header:
            self.in_date_header = False
            date_text = self.text_buffer.strip()
            if self._is_date_header(date_text):
                self.current_date = self._parse_date(date_text)
                self.current_court = None
        elif tag == 'div' and self.in_court_header:
            self.in_court_header = False
            court_text = self.text_buffer.strip()
            if self._is_court_header(court_text):
                self.current_court = court_text
        elif tag == 'span':
            if self.in_category:
                self.in_category = False
                self.current_event['category'] = self.text_buffer.strip()
            elif self.in_time:
                self.in_time = False
                self.current_event['time'] = self.text_buffer.strip()
            elif self.in_broadcaster:
                self.in_broadcaster = False
                self.current_event['broadcaster'] = self.text_buffer.strip()
                # End of event, save it
                if self.current_date and self.current_court:
                    self.current_event['date'] = self.current_date
                    self.current_event['court'] = self.current_court
                    self.events.append(self.current_event.copy())
                self.current_event = {}
                
    def handle_data(self, data):
        if self.in_date_header or self.in_court_header or self.in_category or self.in_time or self.in_broadcaster:
            self.text_buffer += data
            
    def _is_date_header(self, text: str) -> bool:
        """Check if text looks like a date header."""
        date_patterns = [
            r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)',
            r'(January|February|March|April|May|June|July|August|September|October|November|December)',
            r'\d{1,2}'
        ]
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in date_patterns)
        
    def _is_court_header(self, text: str) -> bool:
        """Check if text looks like a court header."""
        return 'court' in text.lower()
        
    def _parse_date(self, date_text: str) -> Optional[str]:
        """Parse date text into a standardized format."""
        # Handle formats like "Thursday, August 28", "Friday, August 29", etc.
        match = re.search(r'(\w+),?\s+(\w+)\s+(\d+)', date_text)
        if match:
            weekday, month, day = match.groups()
            # For now, assume current year (could be enhanced to extract year from page)
            year = datetime.now().year
            try:
                # Convert month name to number
                month_num = datetime.strptime(month, '%B').month
                return f"{year}-{month_num:02d}-{int(day):02d}"
            except ValueError:
                pass
        return None


def fetch_html(url: str) -> Optional[str]:
    """Fetch HTML content from URL."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=30) as response:
            content = response.read()
            # Handle potential encoding issues
            try:
                return content.decode('utf-8')
            except UnicodeDecodeError:
                return content.decode('latin-1')
    except (URLError, HTTPError) as e:
        print(f"Error fetching URL {url}: {e}", file=sys.stderr)
        return None


def parse_schedule_content(html_content: str) -> List[Dict[str, Any]]:
    """Parse HTML content and extract schedule events."""
    # First try the structured parser
    parser = PPAScheduleParser()
    parser.feed(html_content)
    
    if parser.events:
        return parser.events
    
    # Fallback: Simple regex-based parsing
    events = []
    
    # Extract date sections
    date_pattern = r'<h[2-3][^>]*>([^<]*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[^<]*)</h[2-3]>'
    court_pattern = r'<h[3-4][^>]*>([^<]*[Cc]ourt[^<]*)</h[3-4]>'
    
    # Look for patterns in the HTML
    lines = html_content.split('\n')
    current_date = None
    current_court = None
    
    for line in lines:
        line = line.strip()
        
        # Check for date headers
        date_match = re.search(date_pattern, line, re.IGNORECASE)
        if date_match:
            date_text = html.unescape(date_match.group(1)).strip()
            current_date = parse_date_text(date_text)
            continue
            
        # Check for court headers
        court_match = re.search(court_pattern, line, re.IGNORECASE)
        if court_match:
            current_court = html.unescape(court_match.group(1)).strip()
            continue
            
        # Look for event information in text content
        if current_date and current_court:
            # Simple pattern matching for events
            time_pattern = r'(\d{1,2}:\d{2}\s*(?:AM|PM)\s*ET)\s*-\s*(\d{1,2}:\d{2}\s*(?:AM|PM)\s*ET)'
            time_match = re.search(time_pattern, line, re.IGNORECASE)
            
            if time_match:
                # Extract category and broadcaster from surrounding text
                category_pattern = r'(Singles|Doubles|Mixed\s+Doubles|Men\'?s/Women\'?s\s+Doubles|Championships?|Bronze)'
                broadcaster_pattern = r'(PickleballTV|Tennis\s+Channel|FS[12]|ESPN)'
                
                category_match = re.search(category_pattern, line, re.IGNORECASE)
                broadcaster_match = re.search(broadcaster_pattern, line, re.IGNORECASE)
                
                event = {
                    'date': current_date,
                    'court': current_court,
                    'category': category_match.group(1) if category_match else 'Tournament',
                    'time': f"{time_match.group(1)} - {time_match.group(2)}",
                    'broadcaster': broadcaster_match.group(1) if broadcaster_match else ''
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


def parse_time_range(time_str: str, event_date: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse time range string into UTC datetime strings."""
    # Parse "2:00 PM ET - 10:00 PM ET" format
    match = re.match(r'(\d{1,2}:\d{2}\s*(?:AM|PM))\s*ET\s*-\s*(\d{1,2}:\d{2}\s*(?:AM|PM))\s*ET', time_str, re.IGNORECASE)
    if not match:
        return None, None
    
    start_time, end_time = match.groups()
    
    try:
        # Parse the date
        event_dt = datetime.strptime(event_date, '%Y-%m-%d')
        
        # Parse start time
        start_dt = datetime.strptime(f"{event_date} {start_time}", '%Y-%m-%d %I:%M %p')
        
        # Parse end time
        end_dt = datetime.strptime(f"{event_date} {end_time}", '%Y-%m-%d %I:%M %p')
        
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
        
        return start_utc.strftime('%Y-%m-%dT%H:%M:%SZ'), end_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
        
    except ValueError as e:
        print(f"Error parsing time range '{time_str}': {e}", file=sys.stderr)
        return None, None


def ics_escape(value: str) -> str:
    """Escape special characters for ICS format."""
    return (
        value.replace("\\", "\\\\")
             .replace(";", "\\;")
             .replace(",", "\\,")
             .replace("\n", "\\n")
    )


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


def create_ics_event(event: Dict[str, Any], tournament_name: str, dtstamp: str) -> List[str]:
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


def write_ics_file(filename: str, events: List[Dict[str, Any]], tournament_name: str):
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
    
    # Write file
    ics_content = "\r\n".join(lines) + "\r\n"
    with open(filename, "w", encoding="utf-8", newline="") as f:
        f.write(ics_content)
    
    print(f"Created {filename} with {len(events)} events")


def main():
    parser = argparse.ArgumentParser(description="Generate ICS calendar for PPA tournament schedules")
    parser.add_argument("--url", help="PPA tournament schedule URL")
    parser.add_argument("--file", help="Local HTML file to parse")
    parser.add_argument("--tournament", default="Tournament", help="Tournament name")
    parser.add_argument("--output", default="ppa_schedule.ics", help="Output ICS filename")
    parser.add_argument("--debug", action="store_true", help="Print debug information")
    
    args = parser.parse_args()
    
    if not args.url and not args.file:
        print("Error: Must specify either --url or --file", file=sys.stderr)
        sys.exit(1)
    
    # Get HTML content
    if args.url:
        if args.debug:
            print(f"Fetching content from: {args.url}")
        html_content = fetch_html(args.url)
        if not html_content:
            print("Failed to fetch HTML content", file=sys.stderr)
            sys.exit(1)
    else:
        if args.debug:
            print(f"Reading content from: {args.file}")
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except IOError as e:
            print(f"Error reading file {args.file}: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Parse schedule
    events = parse_schedule_content(html_content)
    
    if args.debug:
        print(f"Found {len(events)} events:")
        for event in events:
            print(f"  {event['date']} - {event['court']} - {event['category']} - {event['time']} - {event.get('broadcaster', 'No broadcaster')}")
    
    if not events:
        print("No events found in the HTML content", file=sys.stderr)
        sys.exit(1)
    
    # Write ICS file
    write_ics_file(args.output, events, args.tournament)


if __name__ == "__main__":
    main()
