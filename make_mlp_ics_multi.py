#!/usr/bin/env python3
"""
Fetch MLP matchups for today + next 4 days and generate a combined ICS.

Calendar name is fixed to "MLP Matchups" (no date range in the name).

Endpoint:
  https://majorleaguepickleball.co/wp-json/fau-scores-and-stats/v1/single-event
  with query params:
    query_by_schedule_uuid=true
    schedule_group_uuid=141fe139-b4d2-4846-ac9f-a36b5dd6db41
    division_uuid=5668ed34-5aa6-494d-808f-f5512ae89379
    selected_date=YYYY-MM-DD  # varied for each day

Usage:
  python make_mlp_ics_multi.py --output mlp_matchups.ics
  # Optional:
  python make_mlp_ics_multi.py --days 5 --tz America/Los_Angeles --output mlp_matchups.ics
"""

import sys
import json
import argparse
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    ZoneInfo = None  # Fallback to system local time if not available

# Base URL from the prompt (we will replace selected_date per day)
DEFAULT_URL = (
    "https://majorleaguepickleball.co/wp-json/fau-scores-and-stats/v1/single-event"
    "?query_by_schedule_uuid=true"
    "&schedule_group_uuid=141fe139-b4d2-4846-ac9f-a36b5dd6db41"
    "&division_uuid=5668ed34-5aa6-494d-808f-f5512ae89379"
    "&selected_date=2025-08-17"
)

# Map API court short codes to friendly names
COURT_MAP = {
    "GS": "Grandstand Court",
    "CC": "Center Court",
}

def ics_escape(value: str) -> str:
    # RFC 5545 escaping
    return (
        value.replace("\\", "\\\\")
             .replace(";", "\\;")
             .replace(",", "\\,")
             .replace("\n", "\\n")
    )

def fold_ical_line(line: str, limit: int = 75) -> List[str]:
    # Soft fold per RFC 5545 (approx by character count)
    if len(line) <= limit:
        return [line]
    parts = [line[:limit]]
    s = line[limit:]
    while s:
        parts.append(" " + s[:limit])
        s = s[limit:]
    return parts

def fmt_dt_utc(dt_str: str) -> str:
    # "2025-08-15T17:00:00Z" -> "20250815T170000Z"
    return (
        dt_str.replace("-", "")
              .replace(":", "")
              .replace(".000", "")
              .replace("T", "T")
              .replace("Z", "Z")
    )

def pick_court_name(matchup: Dict[str, Any]) -> Optional[str]:
    """
    Choose a court label for the whole matchup:
    - Prefer the most common 'court_title' among sub-matches (e.g., 'GS', 'CC').
    - Else, if exactly one unique court exists in 'courts', use that.
    - Map via COURT_MAP; else default to "<title> Court".
    """
    titles = [m.get("court_title") for m in matchup.get("matches", []) if m.get("court_title")]
    title = None
    if titles:
        title = max(set(titles), key=titles.count)
    if not title:
        courts = [c.get("title") for c in matchup.get("courts", []) if c.get("title")]
        if courts and len(set(courts)) == 1:
            title = courts[0]
    if not title:
        return None
    return COURT_MAP.get(title, f"{title} Court")

def _coalesce_full_name(full: Optional[str], first: Optional[str], last: Optional[str]) -> Optional[str]:
    if full and full.strip():
        return full.strip()
    if first or last:
        first = (first or "").strip()
        last = (last or "").strip()
        name = (first + " " + last).strip()
        return name if name else None
    return None

def extract_players(matchup: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Return (team_two_players, team_one_players) as sorted unique lists of names.
    We list 'away' (team_two) first to match the title order.
    """
    t1: set[str] = set()
    t2: set[str] = set()

    for m in matchup.get("matches", []) or []:
        # Team One (home)
        p = _coalesce_full_name(m.get("team_one_player_one_name"),
                                m.get("team_one_player_one_first_name"),
                                m.get("team_one_player_one_last_name"))
        if p: t1.add(p)
        p = _coalesce_full_name(m.get("team_one_player_two_name"),
                                m.get("team_one_player_two_first_name"),
                                m.get("team_one_player_two_last_name"))
        if p: t1.add(p)

        # Team Two (away)
        p = _coalesce_full_name(m.get("team_two_player_one_name"),
                                m.get("team_two_player_one_first_name"),
                                m.get("team_two_player_one_last_name"))
        if p: t2.add(p)
        p = _coalesce_full_name(m.get("team_two_player_two_name"),
                                m.get("team_two_player_two_first_name"),
                                m.get("team_two_player_two_last_name"))
        if p: t2.add(p)

    # Stable alphabetical order
    return (sorted(t2), sorted(t1))

def build_event(matchup: Dict[str, Any], dtstamp_utc: str) -> List[str]:
    start = fmt_dt_utc(matchup["planned_start_date"])
    end = fmt_dt_utc(matchup["planned_end_date"])
    away = (matchup.get("team_two_title") or "").strip()
    home = (matchup.get("team_one_title") or "").strip()

    court_name = pick_court_name(matchup)
    summary = f"{away} vs. {home}" if not court_name else f"{away} vs. {home} ({court_name})"

    # Base description (league & event group)
    desc_parts = []
    league = matchup.get("team_league_title")
    group = matchup.get("matchup_group_title")
    if league or group:
        desc_parts.append(" — ".join([p for p in [league, group] if p]))

    # Append players if available
    away_players, home_players = extract_players(matchup)
    roster_lines = []
    if away_players:
        roster_lines.append(f"{away}: " + "; ".join(away_players))
    if home_players:
        roster_lines.append(f"{home}: " + "; ".join(home_players))
    if roster_lines:
        if desc_parts:
            desc_parts.append("")  # blank line between header and rosters
        desc_parts.append("Players (if listed):")
        desc_parts.extend(roster_lines)

    description = "\n".join(desc_parts) if desc_parts else ""

    location = matchup.get("venue", "")
    uid = f"{matchup.get('uuid','unknown')}@mlp"

    event_lines = [
        "BEGIN:VEVENT",
        f"UID:{ics_escape(uid)}",
        f"DTSTAMP:{dtstamp_utc}",
        f"DTSTART:{start}",
        f"DTEND:{end}",
        f"SUMMARY:{ics_escape(summary)}",
        f"LOCATION:{ics_escape(location)}",
        f"DESCRIPTION:{ics_escape(description)}",
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
        "END:VEVENT",
    ]
    out = []
    for line in event_lines:
        out.extend(fold_ical_line(line))
    return out

def update_url_selected_date(url: str, date_str: str) -> str:
    """Replace/insert selected_date=YYYY-MM-DD in the URL query."""
    parts = urlparse(url)
    q = parse_qs(parts.query)
    q["selected_date"] = [date_str]
    new_query = urlencode(
        {k: (v[0] if isinstance(v, list) and len(v) == 1 else v) for k, v in q.items()},
        doseq=True
    )
    return urlunparse((parts.scheme, parts.netloc, parts.path, parts.params, new_query, parts.fragment))

def fetch_json(url: str) -> Optional[Dict[str, Any]]:
    req = Request(url, headers={"User-Agent": "mlp-ics-generator/1.1"})
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except (HTTPError, URLError) as e:
        print(f"WARN: Failed to fetch {url} -> {e}", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"WARN: Bad JSON from {url} -> {e}", file=sys.stderr)
    return None

def collect_matchups_for_dates(base_url: str, days: int, tz_name: str) -> List[Dict[str, Any]]:
    tz = ZoneInfo(tz_name) if (ZoneInfo and tz_name) else None
    now = datetime.now(tz) if tz else datetime.now()
    today_local = now.date()

    all_matchups: Dict[str, Dict[str, Any]] = {}  # uuid -> matchup (dedupe by uuid)

    for i in range(days):
        day = today_local + timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        u = update_url_selected_date(base_url, date_str)
        data = fetch_json(u)
        if not data:
            continue
        mm = (data.get("results") or {}).get("system_matchups") or []
        for m in mm:
            uuid = m.get("uuid")
            if uuid and uuid not in all_matchups:
                all_matchups[uuid] = m

    return list(all_matchups.values())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", "-o", default="mlp_matchups.ics", help="Path to write ICS")
    ap.add_argument("--url", default=DEFAULT_URL, help="Base URL (selected_date will be replaced)")
    ap.add_argument("--days", type=int, default=5, help="Number of days starting today (default 5)")
    ap.add_argument("--tz", default="America/Los_Angeles", help="Timezone for 'today' (IANA name)")
    args = ap.parse_args()

    matchups = collect_matchups_for_dates(args.url, args.days, args.tz)
    if not matchups:
        print("No matchups found for the requested date range.", file=sys.stderr)
        sys.exit(1)

    dtstamp_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines: List[str] = []
    lines.append("BEGIN:VCALENDAR")
    lines.append("VERSION:2.0")
    lines.append("PRODID:-//MLP ICS Generator//EN")
    lines.append("CALSCALE:GREGORIAN")
    lines.append("METHOD:PUBLISH")
    lines.append("X-WR-CALNAME:MLP Matchups")          # <-- fixed name (no dates)
    lines.append(f"X-WR-TIMEZONE:{ics_escape(args.tz)}")

    # Stable order: by planned_start_date
    matchups.sort(key=lambda m: m.get("planned_start_date", ""))

    for mu in matchups:
        try:
            lines.extend(build_event(mu, dtstamp_utc))
        except KeyError as e:
            print(f"WARN: Skipping matchup missing required field {e}: {mu.get('uuid')}", file=sys.stderr)

    lines.append("END:VCALENDAR")
    ics_text = "\r\n".join(lines) + "\r\n"

    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        f.write(ics_text)

    # Also print to stdout
    sys.stdout.write(ics_text)

if __name__ == "__main__":
    main()
