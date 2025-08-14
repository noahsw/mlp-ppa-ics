#!/usr/bin/env python3
"""
Generate ICS calendars for MLP:
- Combined (Premier + Challenger, all courts): mlp.ics
- Premier (all courts): mlp-premier.ics
- Premier Grandstand: mlp-premier-grandstand.ics
- Premier Championship: mlp-premier-championship.ics
- Challenger (all courts): mlp-challenger.ics
- Challenger Grandstand: mlp-challenger-grandstand.ics
- Challenger Championship: mlp-challenger-championship.ics

Pulls data for today + next 4 days (configurable via --days).
Calendar display name (X-WR-CALNAME) is fixed to "MLP Matchups".
Event titles always use full court names when known, never two-letter codes.

Court mapping:
  "GS" -> "Grandstand Court"
  "CC" -> "Championship Court"

Usage:
  python make_mlp_ics_splits.py
  # Options:
  python make_mlp_ics_splits.py --days 5 --tz America/Los_Angeles
"""

import sys
import json
import argparse
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    ZoneInfo = None

BASE_ENDPOINT = "https://majorleaguepickleball.co/wp-json/fau-scores-and-stats/v1/single-event"
SCHEDULE_GROUP_UUID = "141fe139-b4d2-4846-ac9f-a36b5dd6db41"

DIVISIONS = {
    "Premier": "5668ed34-5aa6-494d-808f-f5512ae89379",
    "Challenger": "6fa08298-bfda-40c9-86bc-4e369aac8b77",
}

# Court code -> (friendly label, slug)
COURT_LABELS = {
    "GS": ("Grandstand Court", "grandstand"),
    "CC": ("Championship Court", "championship"),
}

def build_url(selected_date: str, division_uuid: str) -> str:
    q = {
        "query_by_schedule_uuid": "true",
        "schedule_group_uuid": SCHEDULE_GROUP_UUID,
        "division_uuid": division_uuid,
        "selected_date": selected_date,
    }
    return f"{BASE_ENDPOINT}?{urlencode(q)}"

def ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
             .replace(";", "\\;")
             .replace(",", "\\,")
             .replace("\n", "\\n")
    )

def fold_ical_line(line: str, limit: int = 75) -> List[str]:
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

def fetch_json(url: str) -> Optional[Dict[str, Any]]:
    req = Request(url, headers={"User-Agent": "mlp-ics-generator/2.1"})
    try:
        with urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except (HTTPError, URLError) as e:
        print(f"WARN: Failed to fetch {url} -> {e}", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"WARN: Bad JSON from {url} -> {e}", file=sys.stderr)
    return None

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
    Return (away_players, home_players) for the matchup, unique + sorted.
    team_two = away, team_one = home.
    """
    t1: set[str] = set()
    t2: set[str] = set()
    for m in matchup.get("matches", []) or []:
        # Home (team_one)
        p = _coalesce_full_name(m.get("team_one_player_one_name"),
                                m.get("team_one_player_one_first_name"),
                                m.get("team_one_player_one_last_name"))
        if p: t1.add(p)
        p = _coalesce_full_name(m.get("team_one_player_two_name"),
                                m.get("team_one_player_two_first_name"),
                                m.get("team_one_player_two_last_name"))
        if p: t1.add(p)
        # Away (team_two)
        p = _coalesce_full_name(m.get("team_two_player_one_name"),
                                m.get("team_two_player_one_first_name"),
                                m.get("team_two_player_one_last_name"))
        if p: t2.add(p)
        p = _coalesce_full_name(m.get("team_two_player_two_name"),
                                m.get("team_two_player_two_first_name"),
                                m.get("team_two_player_two_last_name"))
        if p: t2.add(p)
    return (sorted(t2), sorted(t1))

def primary_court_code(matchup: Dict[str, Any]) -> Optional[str]:
    """
    Choose a primary court by majority of sub-match 'court_title' (e.g., 'GS', 'CC').
    If none found, and 'courts' has a single unique title, use it.
    """
    titles = [m.get("court_title") for m in matchup.get("matches", []) if m.get("court_title")]
    code = None
    if titles:
        uniq = list(set(titles))
        code = max(uniq, key=titles.count)
    if not code:
        courts = [c.get("title") for c in matchup.get("courts", []) if c.get("title")]
        if courts and len(set(courts)) == 1:
            code = courts[0]
    return code

def court_label_from_code(code: Optional[str]) -> Optional[str]:
    """
    Map known short codes to full labels. If unknown, return None to avoid showing
    a two-letter abbreviation in the event title.
    """
    if not code:
        return None
    label_slug = COURT_LABELS.get(code)
    if label_slug:
        return label_slug[0]  # full label
    return None  # don't fallback to "XX Court" to avoid abbreviations

def build_event(matchup: Dict[str, Any], dtstamp_utc: str, division_name: str) -> List[str]:
    start = fmt_dt_utc(matchup["planned_start_date"])
    end = fmt_dt_utc(matchup["planned_end_date"])
    away = (matchup.get("team_two_title") or "").strip()
    home = (matchup.get("team_one_title") or "").strip()

    code = primary_court_code(matchup)
    court_label = court_label_from_code(code)
    summary = f"{away} vs. {home}" if not court_label else f"{away} vs. {home} ({court_label})"

    desc_parts = []
    league = matchup.get("team_league_title")
    group = matchup.get("matchup_group_title")
    header_line = " — ".join([p for p in [league, group] if p])
    if header_line:
        desc_parts.append(header_line)
    # Division line
    desc_parts.append(f"Division: {division_name}")

    # Players
    away_players, home_players = extract_players(matchup)
    roster_lines = []
    if away_players:
        roster_lines.append(f"{away}: " + "; ".join(away_players))
    if home_players:
        roster_lines.append(f"{home}: " + "; ".join(home_players))
    if roster_lines:
        desc_parts.append("")  # blank line
        desc_parts.append("Players (if listed):")
        desc_parts.extend(roster_lines)

    description = "\n".join(desc_parts)
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

def collect_matchups_for_division(division_name: str, division_uuid: str, days: int, tz_name: str) -> List[Dict[str, Any]]:
    tz = ZoneInfo(tz_name) if (ZoneInfo and tz_name) else None
    now = datetime.now(tz) if tz else datetime.now()
    today_local = now.date()

    dedup: Dict[str, Dict[str, Any]] = {}
    for i in range(days):
        day = today_local + timedelta(days=i)
        url = build_url(day.strftime("%Y-%m-%d"), division_uuid)
        data = fetch_json(url)
        if not data:
            continue
        mm = (data.get("results") or {}).get("system_matchups") or []
        for m in mm:
            uuid = m.get("uuid")
            if uuid and uuid not in dedup:
                m["_division_name"] = division_name  # tag for downstream DESCRIPTION
                dedup[uuid] = m

    lst = list(dedup.values())
    lst.sort(key=lambda m: m.get("planned_start_date", ""))
    return lst

def write_ics(path: str, matchups: List[Dict[str, Any]], tz_name: str):
    dtstamp_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines: List[str] = []
    lines.append("BEGIN:VCALENDAR")
    lines.append("VERSION:2.0")
    lines.append("PRODID:-//MLP ICS Generator//EN")
    lines.append("CALSCALE:GREGORIAN")
    lines.append("METHOD:PUBLISH")
    lines.append("X-WR-CALNAME:MLP Matchups")  # fixed calendar name
    lines.append(f"X-WR-TIMEZONE:{ics_escape(tz_name)}")

    for mu in matchups:
        try:
            lines.extend(build_event(mu, dtstamp_utc, mu.get("_division_name", "")))
        except KeyError as e:
            print(f"WARN: Skipping matchup missing required field {e}: {mu.get('uuid')}", file=sys.stderr)

    lines.append("END:VCALENDAR")
    ics_text = "\r\n".join(lines) + "\r\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(ics_text)

def filter_by_primary_court(matchups: List[Dict[str, Any]], want_code: str) -> List[Dict[str, Any]]:
    out = []
    for m in matchups:
        code = primary_court_code(m)
        if code == want_code:
            out.append(m)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=5, help="Number of days starting today (default 5)")
    ap.add_argument("--tz", default="America/Los_Angeles", help="Timezone for 'today' (IANA name)")
    args = ap.parse_args()

    # Collect each division
    premier = collect_matchups_for_division("Premier", DIVISIONS["Premier"], args.days, args.tz)
    challenger = collect_matchups_for_division("Challenger", DIVISIONS["Challenger"], args.days, args.tz)

    # Combined (dedupe by uuid across both)
    combined_map: Dict[str, Dict[str, Any]] = {}
    for lst in (premier, challenger):
        for m in lst:
            combined_map[m["uuid"]] = m
    combined = list(combined_map.values())
    combined.sort(key=lambda m: m.get("planned_start_date", ""))

    # Write the seven calendars
    write_ics("mlp.ics", combined, args.tz)

    write_ics("mlp-premier.ics", premier, args.tz)
    write_ics("mlp-challenger.ics", challenger, args.tz)

    # Per-court: Grandstand (GS)
    premier_gs = filter_by_primary_court(premier, "GS")
    challenger_gs = filter_by_primary_court(challenger, "GS")
    write_ics("mlp-premier-grandstand.ics", premier_gs, args.tz)
    write_ics("mlp-challenger-grandstand.ics", challenger_gs, args.tz)

    # Per-court: Championship (CC)
    premier_cc = filter_by_primary_court(premier, "CC")
    challenger_cc = filter_by_primary_court(challenger, "CC")
    write_ics("mlp-premier-championship.ics", premier_cc, args.tz)
    write_ics("mlp-challenger-championship.ics", challenger_cc, args.tz)

    # Quick summary to stdout
    def count_lineup(name: str, lst: List[Dict[str, Any]]):
        print(f"{name}: {len(lst)} events")

    print("Wrote ICS files:")
    count_lineup("mlp", combined)
    count_lineup("mlp-premier", premier)
    count_lineup("mlp-premier-grandstand", premier_gs)
    count_lineup("mlp-premier-championship", premier_cc)
    count_lineup("mlp-challenger", challenger)
    count_lineup("mlp-challenger-grandstand", challenger_gs)
    count_lineup("mlp-challenger-championship", challenger_cc)

if __name__ == "__main__":
    main()
