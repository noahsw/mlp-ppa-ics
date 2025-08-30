# MLP & PPA Matchups → iCalendar (ICS)

Generate live-updating **.ics** calendars for both Major League Pickleball (MLP) matchups and Professional Pickleball Association (PPA) tournament schedules that your phone or desktop calendar can subscribe to.

![Screenshot of calendar](https://github.com/noahsw/mlp-ppa-ics/blob/main/screenshot.jpg?raw=true)

---

## MLP Calendar Subscriptions

Use any of these URLs when subscribing (pick one or many):

- **Combined (Premier + Challenger, all courts):** https://noahsw.github.io/mlp-ppa-ics/mlp.ics

- **Premier (all courts):** https://noahsw.github.io/mlp-ppa-ics/mlp-premier.ics

- **Premier — Grandstand Court:** https://noahsw.github.io/mlp-ppa-ics/mlp-premier-grandstand.ics

- **Premier — Championship Court:** https://noahsw.github.io/mlp-ppa-ics/mlp-premier-championship.ics

- **Challenger (all courts):** https://noahsw.github.io/mlp-ppa-ics/mlp-challenger.ics

- **Challenger — Grandstand Court:** https://noahsw.github.io/mlp-ppa-ics/mlp-challenger-grandstand.ics

- **Challenger — Championship Court:** https://noahsw.github.io/mlp-ppa-ics/mlp-challenger-championship.ics

---

## PPA Calendar Subscriptions

Use any of these URLs when subscribing (pick one or many):

- **All:** https://noahsw.github.io/mlp-ppa-ics/ppa.ics

- **Championships:** https://noahsw.github.io/mlp-ppa-ics/ppa-championships.ics

---

## Subscribe instructions
These steps are the same for **any** of the Calendar URLs above.

### iPhone / iPad (iOS)

1. **Settings → Calendar → Accounts → Add Account → Other → Add Subscribed Calendar**
2. Paste the URL above → **Next** → optionally set a name → **Save**.
3. Open the Calendar app and ensure the new calendar is checked (visible).

### Android (Google Calendar account)

> Google Calendar mobile app doesn't add URL subscriptions directly. Add it on the web and it will sync to your phone.

1. Go to **calendar.google.com** (web) → left sidebar **Other calendars → From URL**.
2. Paste the URL → **Add calendar**.
3. On your phone, open Google Calendar → ensure the calendar is toggled on: **☰ → Settings → your account → the subscribed calendar**.

### Android (Samsung Calendar)

Samsung Calendar will display calendars from your Google account. Follow the **Google Calendar** steps above, then in **Samsung Calendar → ☰ → Calendars**, make sure the subscribed calendar (under your Google account) is enabled.

### macOS (Apple Calendar)

1. **Calendar → File → New Calendar Subscription…**
2. Paste the URL → **Subscribe**.
3. Set auto‑refresh (e.g., every 15 minutes) and a name → **OK**.

### Microsoft Outlook

* **Outlook on the web (OWA):** **Add calendar → Subscribe from web** → paste URL → name it → **Import**.
* **New Outlook (Windows/macOS):** **Add calendar → Subscribe from web** → paste URL → **Add**.
* **Classic Outlook for Windows:** **File → Account Settings → Internet Calendars → New…** → paste URL → **Add**.

> **Refresh timing:** Different apps refresh on their own schedule (often 15–60 minutes; Google may cache longer). This repo updates the feed hourly.

---

## What this repo does

### MLP Calendar Generation

* Fetches active tournaments from: `https://majorleaguepickleball.co/wp-json/fau-scores-and-stats/v1/event-matches`
* Fetches matchups from: `https://majorleaguepickleball.co/wp-json/fau-scores-and-stats/v1/single-event`
* Pulls data for **yesterday + today + next 4 days** (configurable via `--days`).
* Only fetches matchups for tournaments whose dates overlap with the date range (avoids fetching old or far-future events).
* De‑dupes by `system_matchups.uuid` and sorts by `planned_start_date`.
* Emits **UTC** start/end times (your calendar renders them in local time).
* **Event title**: `Away vs. Home (Court)` — e.g., `Miami Pickleball Club vs. Texas Ranchers (Grandstand Court)`.
* **Court names** mapped (`GS → Grandstand Court`, `CC → Championship Court`), unknown codes default to `"<code> Court"`.
* **DESCRIPTION** includes league + event group, **final scores** for completed matches, and **player names** when available.
* Calendar display name is fixed to **MLP Matchups**.

### PPA Calendar Generation

* Scrapes PPA tournament schedule pages from `ppatour.com`
* Parses tournament event details including dates, times, courts, categories, and broadcasters
* Supports both direct tournament URLs and automatic tournament discovery from schedule pages
* Converts Eastern Time to UTC for proper calendar display
* Generates ICS files with complete event information and proper formatting

---

## Technical details

### Repo layout

```
.
├─ make_mlp_ics_multi.py           # MLP calendar generation
├─ make_ppa_ics.py                 # PPA calendar generation
├─ run_tests.py                    # Test runner for all tests
├─ run_ppa_tests.py                # PPA-specific test runner
├─ test_mlp_ics.py                 # MLP test suite
├─ test_ppa_parser.py              # PPA test suite
├─ sample_*.html                   # Sample HTML files for testing
├─ sample_*.json                   # Sample API responses for testing
└─ .github/
   └─ workflows/
      └─ build-ics.yml             # GitHub Actions workflow (hourly)
```

### Requirements

* **Python 3.9+** (uses `zoneinfo`).
* No third‑party packages; standard library only.

### Running locally

#### MLP Calendars
```bash
python make_mlp_ics_multi.py
```

Options:
* `--days 5` – number of days after yesterday (default 5, includes yesterday + today + next 3 days)
* `--tz America/Los_Angeles` – timezone used to compute "today" (default `America/Los_Angeles`)
* `--debug` – print verbose debug info (titles, counts, URLs)

#### PPA Calendars
Usage:
  python make_ppa_ics.py --tournament-schedule-url https://www.ppatour.com/tournament/2025/open-at-the-las-vegas-strip/#schedule
  python make_ppa_ics.py --tour-schedule-url https://www.ppatour.com/schedule/
  python make_ppa_ics.py --tournament-schedule-file sample_ppa_tournament_schedule.html --tournament "Open at the Las Vegas Strip"
  python make_ppa_ics.py --tour-schedule-file sample_ppa_tour_schedule.html
  python make_ppa_ics.py --tour-schedule-url https://www.ppatour.com/schedule/ --championships-only

Options:
* `--output filename.ics` – specify output filename (default: ppa.ics, or ppa-championships.ics if --championships-only)
* `--championships-only` – filter to only championship/finals events (creates ppa-championships.ics by default)
* `--debug` – print verbose parsing information

### Testing

The project includes comprehensive test coverage for both MLP and PPA ICS generation logic.

#### Running tests

```bash
# Run all tests with detailed output
python run_tests.py

# Run only PPA tests
python run_ppa_tests.py

# Run only MLP tests
python test_mlp_ics.py

# Run tests using unittest directly
python -m unittest test_mlp_ics.py test_ppa_parser.py -v
```

#### Test coverage includes

**MLP Tests:**
* Completed matchups with scores
* In-progress matchups
* Upcoming matchups
* Court filtering and naming
* Player name extraction
* ICS formatting and escaping
* Edge cases and error handling

**PPA Tests:**
* HTML parsing from tournament pages
* Date and time range parsing with timezone conversion
* Event creation and ICS file generation
* Tournament URL extraction from schedule pages
* Broadcaster detection
* Command line interface
* Error handling and edge cases
* Full integration testing

### Manual execution

```bash
# Generate MLP calendars
python make_mlp_ics_multi.py --debug

# Generate PPA calendar
python make_ppa_ics.py --debug
```

### Customization

#### MLP Customization
* **Court names**: edit `COURT_MAP` in `make_mlp_ics_multi.py`.
* **Calendar name**: fixed to `X-WR-CALNAME: MLP Matchups` (change in script if desired).
* **Days & timezone**: set via `--days` and `--tz`.
* **Players section**: pulled from per‑match fields; omitted automatically if unavailable.

#### PPA Customization
* **Tournament parsing**: edit parsing logic in `parse_ppa_website_structure()` function
* **Broadcaster detection**: extend broadcaster URL patterns in parsing logic
* **Calendar naming**: modify `X-WR-CALNAME` generation in `write_ics_file()` function
* **Timezone handling**: adjust Eastern Time conversion logic in `parse_time_range()`

### Troubleshooting

* **No events**: Check Actions logs. The APIs can return empty for certain dates.
* **Calendar not updating**: client caching. Subscribed calendars refresh on their own schedule.
* **Unknown court code**: extend `COURT_MAP` in MLP script.
* **PPA parsing issues**: Use `--debug` flag to see detailed parsing information.
* **Tournament not found**: Verify the tournament URL format matches PPA website structure.


### Caveats

* Unofficial; upstream APIs and website structures may change.
* Minimal error handling by design; warnings print to Action logs.
* MLP: Approx request volume: 1 request/day × 5 days × hourly.
* PPA: Requires manual generation per tournament; no automatic scheduling yet.

### License

MIT. No warranty.
