
#!/usr/bin/env python3
"""
Shared ICS utility functions for both MLP and PPA calendar generators.

Contains common functionality for:
- ICS special character escaping
- ICS line folding 
- ICS file structure helpers
"""

from typing import List


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


def get_ics_header(calendar_name: str, timezone: str = "America/New_York") -> List[str]:
    """Get standard ICS calendar header lines."""
    return [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//MLP-PPA ICS Generator//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{ics_escape(calendar_name)}",
        f"X-WR-TIMEZONE:{ics_escape(timezone)}",
    ]


def get_ics_footer() -> List[str]:
    """Get standard ICS calendar footer lines."""
    return ["END:VCALENDAR"]


def fold_event_lines(event_lines: List[str]) -> List[str]:
    """Apply line folding to all event lines."""
    folded_lines = []
    for line in event_lines:
        folded_lines.extend(fold_ical_line(line))
    return folded_lines
