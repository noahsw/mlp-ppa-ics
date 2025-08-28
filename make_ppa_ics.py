
#!/usr/bin/env python3
"""
Generate ICS calendar for PPA tournament schedules.

Scrapes PPA tournament schedule pages and generates ICS calendar files.
Can work with both live URLs and local HTML files for testing.

Usage:
  python make_ppa_ics.py --url https://www.ppatour.com/tournament/2025/open-at-the-las-vegas-strip/#schedule
  python make_ppa_ics.py --file sample_ppa_schedule.html --tournament "Open at the Las Vegas Strip"
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
        self.current_category = None
        self.current_time = None
        self.current_broadcaster = None
        self.in_day_title = False
        self.in_court_title = False
        self.in_event_title = False
        self.in_broadcaster_link = False
        self.text_buffer = ""
        self.depth = 0
        
    def handle_starttag(self, tag, attrs):
        self.depth += 1
        attrs_dict = dict(attrs)
        class_attr = attrs_dict.get('class', '')
        
        # Look for day titles (h3 with date)
        if tag == 'h3' and 'typo-heading--3' in class_attr:
            self.in_day_title = True
            self.text_buffer = ""
        # Look for court titles (h4)
        elif tag == 'h4' and 'typo-heading--4' in class_attr:
            self.in_court_title = True
            self.text_buffer = ""
        # Look for event title divs
        elif tag == 'div' and 'how-to-watch__schedule-event-title' in class_attr:
            self.in_event_title = True
            self.current_category = None
            self.current_time = None
        # Look for broadcaster links
        elif tag == 'a' and 'how-to-watch__schedule-platform' in class_attr:
            self.in_broadcaster_link = True
            href = attrs_dict.get('href', '')
            if 'pickleballtv.com' in href:
                self.current_broadcaster = 'PickleballTV'
            elif 'tennischannel.com' in href:
                self.current_broadcaster = 'Tennis Channel'
            elif 'foxsports.com/live/fs1' in href:
                self.current_broadcaster = 'FS1'
            elif 'foxsports.com/live/fs2' in href:
                self.current_broadcaster = 'FS2'
            else:
                self.current_broadcaster = 'Unknown'
                
    def handle_endtag(self, tag):
        self.depth -= 1
        
        if tag == 'h3' and self.in_day_title:
            self.in_day_title = False
            date_text = self.text_buffer.strip()
            self.current_date = self._parse_date(date_text)
            
        elif tag == 'h4' and self.in_court_title:
            self.in_court_title = False
            self.current_court = self.text_buffer.strip()
            
        elif tag == 'div' and self.in_event_title:
            self.in_event_title = False
            # Parse the event title text for category and time
            event_text = self.text_buffer.strip()
            self._parse_event_text(event_text)
            
        elif tag == 'a' and self.in_broadcaster_link:
            self.in_broadcaster_link = False
            # Save the complete event
            if all([self.current_date, self.current_court, self.current_category, 
                   self.current_time, self.current_broadcaster]):
                event = {
                    'date': self.current_date,
                    'court': self.current_court,
                    'category': self.current_category,
                    'time': self.current_time,
                    'broadcaster': self.current_broadcaster
                }
                self.events.append(event)
                
    def handle_data(self, data):
        if self.in_day_title or self.in_court_title or self.in_event_title:
            self.text_buffer += data
            
    def _parse_event_text(self, text: str):
        """Parse event text like 'Singles | 2:00 PM ET - 10:00 PM ET'."""
        # Handle HTML entities
        text = html.unescape(text)
        
        # Split by pipe
        parts = text.split('|')
        if len(parts) >= 2:
            self.current_category = parts[0].strip()
            self.current_time = parts[1].strip()
        else:
            # Fallback: try to extract category and time separately
            category_match = re.search(r'(Singles|Mixed\s+Doubles|Men\'?s/Women\'?s\s+Doubles|Championships?|Bronze)', text, re.IGNORECASE)
            time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM)\s*ET\s*-\s*\d{1,2}:\d{2}\s*(?:AM|PM)\s*ET)', text, re.IGNORECASE)
            
            if category_match:
                self.current_category = category_match.group(1)
            if time_match:
                self.current_time = time_match.group(1)
        
    def _parse_date(self, date_text: str) -> Optional[str]:
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
    
    # Fallback: Enhanced regex-based parsing for the PPA website structure
    events = []
    
    # Look for the "how-to-watch" schedule section
    schedule_match = re.search(r'<section[^>]*id="how-to-watch"[^>]*>.*?</section>', html_content, re.DOTALL)
    if not schedule_match:
        print("Could not find how-to-watch section", file=sys.stderr)
        return events
    
    schedule_html = schedule_match.group(0)
    
    # Extract day sections
    day_pattern = r'<div class="how-to-watch__schedule-day">(.*?)</div>\s*</div>\s*</div>'
    day_matches = re.finditer(day_pattern, schedule_html, re.DOTALL)
    
    for day_match in day_matches:
        day_content = day_match.group(1)
        
        # Extract date
        date_match = re.search(r'<h3[^>]*class="typo-heading--3"[^>]*>([^<]+)</h3>', day_content)
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
            court_name_match = re.search(r'<h4[^>]*class="typo-heading--4"[^>]*>([^<]+)</h4>', court_content)
            if not court_name_match:
                continue
            
            court_name = html.unescape(court_name_match.group(1)).strip()
            
            # Extract events within this court
            event_pattern = r'<div class="how-to-watch__schedule-event">(.*?)</div>\s*</div>'
            event_matches = re.finditer(event_pattern, court_content, re.DOTALL)
            
            for event_match in event_matches:
                event_content = event_match.group(1)
                
                # Extract category and time
                title_match = re.search(r'<div class="how-to-watch__schedule-event-title">(.*?)</div>', event_content, re.DOTALL)
                if not title_match:
                    continue
                
                title_content = title_match.group(1)
                
                # Extract category (span content)
                category_match = re.search(r'<span[^>]*class="typo-heading--4"[^>]*>([^<]+)</span>', title_content)
                if not category_match:
                    continue
                
                category = html.unescape(category_match.group(1)).strip()
                
                # Extract time (after the pipe)
                time_match = re.search(r'\|\s*<span>([^<]+)</span>', title_content)
                if not time_match:
                    continue
                
                time_text = html.unescape(time_match.group(1)).strip()
                
                # Extract broadcaster
                broadcaster_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>', event_content)
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
