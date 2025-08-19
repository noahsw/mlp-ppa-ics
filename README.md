# MLP Matchups → iCalendar (ICS)

Generate a live-updating **.ics** calendar of Major League Pickleball matchups that your phone or desktop calendar can subscribe to.

---

## Subscribe to this calendar

Use any of these URLs when subscribing (pick one or many):

- **Combined (Premier + Challenger, all courts):** https://noahsw.github.io/mlp-ppa-ics/mlp.ics

- **Premier (all courts):** https://noahsw.github.io/mlp-ppa-ics/mlp-premier.ics

- **Premier — Grandstand Court:** https://noahsw.github.io/mlp-ppa-ics/mlp-premier-grandstand.ics

- **Premier — Championship Court:** https://noahsw.github.io/mlp-ppa-ics/mlp-premier-championship.ics

- **Challenger (all courts):** https://noahsw.github.io/mlp-ppa-ics/mlp-challenger.ics

- **Challenger — Grandstand Court:** https://noahsw.github.io/mlp-ppa-ics/mlp-challenger-grandstand.ics

- **Challenger — Championship Court:** https://noahsw.github.io/mlp-ppa-ics/mlp-challenger-championship.ics


> **Tip:** The combined feed is the easiest starting point. Add per‑division/court feeds if you want selective alerts.

---

## Subscribe instructions
These steps are the same for **any** of the URLs above.

### iPhone / iPad (iOS)

1. **Settings → Calendar → Accounts → Add Account → Other → Add Subscribed Calendar**
2. Paste the URL above → **Next** → optionally set a name → **Save**.
3. Open the Calendar app and ensure the new calendar is checked (visible).

### Android (Google Calendar account)

> Google Calendar mobile app doesn’t add URL subscriptions directly. Add it on the web and it will sync to your phone.

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

---

## Technical details

### Repo layout

```
.
├─ make_mlp_ics_multi.py           # main script
└─ .github/
   └─ workflows/
      └─ build-ics.yml             # GitHub Actions workflow (hourly)
```

### Requirements

* **Python 3.9+** (uses `zoneinfo`).
* No third‑party packages; standard library only.

### Running locally

```bash
python make_mlp_ics_multi.py
```

Options:

* `--days 5` – number of days after yesterday (default 5, includes yesterday + today + next 3 days)
* `--tz America/Los_Angeles` – timezone used to compute "today" (default `America/Los_Angeles`)
* `--debug` – print verbose debug info (titles, counts, URLs)

### Testing

The project includes comprehensive test coverage for the ICS generation logic.

#### Running tests

```bash
# Run all tests with detailed output
python run_tests.py

# Run tests using unittest directly
python test_mlp_ics.py

# Run with pytest (if available)
python -m pytest test_mlp_ics.py -v
```

#### Test files

* **`test_mlp_ics.py`** – Main test suite covering:
  * Completed matchups with scores
  * In-progress matchups
  * Upcoming matchups
  * Court filtering and naming
  * Player name extraction
  * ICS formatting and escaping
  * Edge cases and error handling

* **`test_sample_data.py`** – Generates sample API response data for testing

* **`run_tests.py`** – Test runner with detailed reporting

#### Test coverage includes

* Event title generation with court names
* Score formatting for completed games (including individual match results)
* Player name extraction and display
* ICS special character escaping
* UTC datetime formatting
* API response handling
* Court code mapping
* Division filtering
* Dynamic event fetching and date range filtering
* Edge cases and error handling


### Automation / Deploy (Replit Deployments)

This project can be deployed on Replit using Deployments for automatic hosting and scheduling:

1. **Deploy on Replit**: Use the Deployments feature to publish your project
2. **Schedule updates**: Set up a cron job or periodic task to run the script automatically
3. **Serve files**: The generated `.ics` files will be accessible via your deployment URL

### Manual execution

Run the script directly in Replit:

```bash
python make_mlp_ics_multi.py --debug
```

### Customization

* **Court names**: edit `COURT_MAP` in `make_mlp_ics_multi.py`.
* **Calendar name**: fixed to `X-WR-CALNAME: MLP Matchups` (change in script if desired).
* **Days & timezone**: set via `--days` and `--tz`.
* **Players section**: pulled from per‑match fields; omitted automatically if unavailable.

### Troubleshooting

* **No events**: Check Actions logs. The API can return empty for certain dates.
* **Calendar not updating**: client caching. Subscribed calendars refresh on their own schedule.
* **Unknown court code**: extend `COURT_MAP`.

### Caveats

* Unofficial; upstream API may change.
* Minimal error handling by design; warnings print to Action logs.
* Approx request volume: 1 request/day × 5 days × hourly.

### License

MIT. No warranty.