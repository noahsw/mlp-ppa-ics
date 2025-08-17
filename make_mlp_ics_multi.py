#!/usr/bin/env python3
"""
Generate ICS calendars for MLP:

Outputs (7 files):
- mlp.ics (Premier + Challenger, all courts)
- mlp-premier.ics
- mlp-premier-grandstand.ics
- mlp-premier-championship.ics
- mlp-challenger.ics
- mlp-challenger-grandstand.ics
- mlp-challenger-championship.ics

Pulls data for today + next 4 days (configurable via --days).
Calendar display name (X-WR-CALNAME) is fixed to "MLP Matchups".
Event titles always use full court names when known, never two-letter codes.

Court mapping:
  "GS" -> "Grandstand Court"
  "CC" -> "Championship Court"

Usage:
  python make_mlp_ics_multi.py
  python make_mlp_ics_multi.py --days 5 --tz America/Los_Angeles --debug
"""

import os
import sys
import json
import time
import random
import argparse
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple, Set
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    ZoneInfo = None

# Allow override via env if you ever need to (but default hits MLP directly)
BASE_ENDPOINT = os.getenv(
    "MLP_BASE_ENDPOINT",
    "https://majorleaguepickleball.co/wp-json/fau-scores-and-stats/v1/single-event"
)
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

UA_LIST = [
    # Rotate through a few realistic desktop browsers
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 "
     "(KHTML, like Gecko) Version/17.5 Safari/605.1.15"),
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
]

def build_url(selected_date: str, division_uuid: str) -> str:
    q = {
        "query_by_schedule_uuid": "true",
        "schedule_group_uuid": SCHEDULE_GROUP_UUID,
        "division_uuid": division_uuid,
        "selected_date": selected_date,
    }
    return f"{BASE_ENDPOINT}?{urlencode(q)}"

def _headers(ua: str) -> Dict[str, str]:
    # Use browser-like headers. Avoid Accept-Encoding so Python doesn’t need to decompress.
    return {
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://majorleaguepickleball.co/",
        "Origin": "https://majorleaguepickleball.co",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        # Some WAFs look for these (harmless if ignored by server)
        "sec-ch-ua": "\"Chromium\";v=\"127\", \"Not)A;Brand\";v=\"24\", \"Google Chrome\";v=\"127\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
    }

def fetch_json(url: str, debug: bool = False, max_attempts: int = 4, base_delay: float = 0.8) -> Optional[Dict[str, Any]]:
    """
    Fetch with rotating UAs and backoff. Print status/body snippet on failures.
    """
    # Deterministic-ish rotation across attempts
    idx_order = list(range(len(UA_LIST)))
    random.shuffle(idx_order)

    for attempt in range(1, max_attempts + 1):
        ua = UA_LIST[idx_order[(attempt - 1) % len(UA_LIST)]]
        headers = _headers(ua)
        if debug:
            print(f"[fetch attempt {attempt}/{max_attempts}] {url}")
            print(f"  UA: {ua[:60]}...")

        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=30) as resp:
                status = getattr(resp, "status", resp.getcode())
                body = resp.read().decode("utf-8", errors="replace")
                if debug:
                    print(f"  HTTP {status}, {len(body)} bytes")
                if status != 200:
                    if debug:
                        print(f"  ! Non-200: {status}\n  Body(head): {body[:200]}")
                    raise HTTPError(url, status, f"HTTP {status}", hdrs=None, fp=None)
                return json.loads(body)
        except HTTPError as e:
            code = getattr(e, "code", "HTTPError")
            if debug:
                print(f"  !! HTTPError: {code}")
            # Backoff on retryable statuses; 403 often WAF—still try rotated UA
        except URLError as e:
            if debug:
                print(f"  !! URLError: {e}")
        except json.JSONDecodeError as e:
            if debug:
                print(f"  !! JSONDecodeError: {e}")

        if attempt < max_attempts:
            sleep_s = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.4)
            if debug:
                print(f"  .. retrying in {sleep_s:.1f}s")
            time.sleep(sleep_s)

    # Give up
    if debug:
        print("  xx giving up")
    return None

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
    t1: Set[str] = set()
    t2: Set[str] = set()
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

def make_event_title(matchup: Dict[str, Any]) -> str:
    away = (matchup.get("team_two_title") or "").strip()
    home = (matchup.get("team_one_title") or "").strip()
    code = primary_court_code(matchup)
    court_label = court_label_from_code(code)
    return f"{away} vs. {home}" if not court_label else f"{away} vs. {home} ({court_label})"

def build_event(matchup: Dict[str, Any], dtstamp_utc: str, division_name: str) -> List[str]:
    start = fmt_dt_utc(matchup["planned_start_date"])
    end = fmt_dt_utc(matchup["planned_end_date"])
    away = (matchup.get("team_two_title") or "").strip()
    home = (matchup.get("team_one_title") or "").strip()
    summary = make_event_title(matchup)

    desc_parts = []
    league = matchup.get("team_league_title")
    group = matchup.get("matchup_group_title")
    header_line = " — ".join([p for p in [league, group] if p])
    if header_line:
        desc_parts.append(header_line)
    desc_parts.append(f"Division: {division_name}")

    # Check if matchup is completed and has scores
    matchup_status = matchup.get("matchup_status", "")
    is_completed = matchup_status == "COMPLETED_MATCHUP_STATUS"
    
    if is_completed:
        # Add overall matchup score if available
        team_one_score = matchup.get("team_one_score")
        team_two_score = matchup.get("team_two_score")
        if team_one_score is not None and team_two_score is not None:
            desc_parts.append(f"\nFINAL SCORE: {away} {team_two_score} - {team_one_score} {home}")
        
        # Add individual match scores if available
        matches = matchup.get("matches", [])
        if matches:
            game_scores = []
            for i, match in enumerate(matches, 1):
                match_status = match.get("match_status")
                match_completed_type = match.get("match_completed_type")
                
                # Check if individual match is completed 
                if match_status == 4 and match_completed_type == 5:
                    # Get the actual game scores from the match
                    t1_score = match.get("team_one_score")
                    t2_score = match.get("team_two_score")
                    
                    if t1_score is not None and t2_score is not None:
                        court = match.get("court_title", "")
                        round_text = match.get("round_text", "")
                        
                        # Create descriptive label
                        if round_text:
                            game_label = round_text
                        else:
                            game_label = f"Match {i}"
                        
                        if court:
                            game_label += f" ({court})"
                        
                        game_scores.append(f"{game_label}: {away} {t2_score} - {t1_score} {home}")
            
            if game_scores:
                desc_parts.append("")
                desc_parts.append("Individual Match Results:")
                desc_parts.extend(game_scores)

    away_players, home_players = extract_players(matchup)
    roster_lines = []
    if away_players:
        roster_lines.append(f"{away}: " + "; ".join(away_players))
    if home_players:
        roster_lines.append(f"{home}: " + "; ".join(home_players))
    if roster_lines:
        desc_parts.append("")
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

def collect_matchups_for_division(division_name: str, division_uuid: str, days: int, tz_name: str, debug: bool = False) -> List[Dict[str, Any]]:
    tz = ZoneInfo(tz_name) if (ZoneInfo and tz_name) else None
    now = datetime.now(tz) if tz else datetime.now()
    today_local = now.date()

    if debug:
        print(f"\n== Collecting: {division_name} (next {days} day(s), tz={tz_name}) ==")

    dedup: Dict[str, Dict[str, Any]] = {}
    for i in range(days):
        day = today_local + timedelta(days=i)
        url = build_url(day.strftime("%Y-%m-%d"), division_uuid)
        data = fetch_json(url, debug=debug)
        if not data:
            if debug:
                print(f"[{division_name}] {day} -> no data")
            continue
        mm = (data.get("results") or {}).get("system_matchups") or []
        if debug:
            print(f"[{division_name}] {day} -> {len(mm)} matchup(s)")
        for m in mm:
            uuid = m.get("uuid")
            if uuid and uuid not in dedup:
                m["_division_name"] = division_name
                dedup[uuid] = m

    lst = list(dedup.values())
    lst.sort(key=lambda m: m.get("planned_start_date", ""))
    if debug:
        print(f"[{division_name}] total unique matchups: {len(lst)}")
        for m in lst:
            title = make_event_title(m)
            status = m.get("matchup_status", "")
            is_completed = status == "COMPLETED_MATCHUP_STATUS"
            
            debug_line = f"  - {m.get('planned_start_date','?')}  {title}"
            
            if is_completed:
                team_one_score = m.get("team_one_score")
                team_two_score = m.get("team_two_score")
                if team_one_score is not None and team_two_score is not None:
                    away = (m.get("team_two_title") or "").strip()
                    home = (m.get("team_one_title") or "").strip()
                    debug_line += f" [FINAL: {away} {team_two_score} - {team_one_score} {home}]"
                else:
                    debug_line += " [COMPLETED - no scores]"
            else:
                debug_line += f" [STATUS: {status}]"
            
            print(debug_line)
    return lst

def write_ics(path: str, matchups: List[Dict[str, Any]], tz_name: str, debug: bool = False):
    dtstamp_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines: List[str] = []
    lines.append("BEGIN:VCALENDAR")
    lines.append("VERSION:2.0")
    lines.append("PRODID:-//MLP ICS Generator//EN")
    lines.append("CALSCALE:GREGORIAN")
    lines.append("METHOD:PUBLISH")
    lines.append("X-WR-CALNAME:MLP Matchups")
    lines.append(f"X-WR-TIMEZONE:{ics_escape(tz_name)}")

    for mu in matchups:
        try:
            if debug:
                print(f"[write:{path}] {make_event_title(mu)}")
            lines.extend(build_event(mu, dtstamp_utc, mu.get("_division_name", "")))
        except KeyError as e:
            print(f"WARN: Skipping matchup missing required field {e}: {mu.get('uuid')}", file=sys.stderr)

    lines.append("END:VCALENDAR")
    ics_text = "\r\n".join(lines) + "\r\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(ics_text)
    if debug:
        print(f"[done] Wrote {path} with {len(matchups)} event(s)")

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
    ap.add_argument("--debug", action="store_true", help="Print verbose debug info (titles, counts, URLs)")
    args = ap.parse_args()

    premier = collect_matchups_for_division("Premier", DIVISIONS["Premier"], args.days, args.tz, debug=args.debug)
    challenger = collect_matchups_for_division("Challenger", DIVISIONS["Challenger"], args.days, args.tz, debug=args.debug)

    combined_map: Dict[str, Dict[str, Any]] = {}
    for lst in (premier, challenger):
        for m in lst:
            combined_map[m["uuid"]] = m
    combined = list(combined_map.values())
    combined.sort(key=lambda m: m.get("planned_start_date", ""))

    write_ics("mlp.ics", combined, args.tz, debug=args.debug)

    write_ics("mlp-premier.ics", premier, args.tz, debug=args.debug)
    write_ics("mlp-challenger.ics", challenger, args.tz, debug=args.debug)

    premier_gs = filter_by_primary_court(premier, "GS")
    challenger_gs = filter_by_primary_court(challenger, "GS")
    write_ics("mlp-premier-grandstand.ics", premier_gs, args.tz, debug=args.debug)
    write_ics("mlp-challenger-grandstand.ics", challenger_gs, args.tz, debug=args.debug)

    premier_cc = filter_by_primary_court(premier, "CC")
    challenger_cc = filter_by_primary_court(challenger, "CC")
    write_ics("mlp-premier-championship.ics", premier_cc, args.tz, debug=args.debug)
    write_ics("mlp-challenger-championship.ics", challenger_cc, args.tz, debug=args.debug)

    # Quick summary to stdout
    def count_lineup(name: str, lst: List[Dict[str, Any]]):
        print(f"{name}: {len(lst)} events")
    print("\nSummary:")
    count_lineup("mlp", combined)
    count_lineup("mlp-premier", premier)
    count_lineup("mlp-premier-grandstand", premier_gs)
    count_lineup("mlp-premier-championship", premier_cc)
    count_lineup("mlp-challenger", challenger)
    count_lineup("mlp-challenger-grandstand", challenger_gs)
    count_lineup("mlp-challenger-championship", challenger_cc)

if __name__ == "__main__":
    main()
