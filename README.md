# MLP Matchups → iCalendar (ICS)

Generate a live-updating **.ics** calendar of Major League Pickleball matchups that your phone or desktop calendar can subscribe to.

---

## Subscribe to this calendar

**Calendar URL:**

```
https://noahsw.github.io/mlp-ppa-ics/mlp.ics
```

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

* Fetches matchups from:
  `https://majorleaguepickleball.co/wp-json/fau-scores-and-stats/v1/single-event`
  with query params:

  * `query_by_schedule_uuid=true`
  * `schedule_group_uuid=141fe139-b4d2-4846-ac9f-a36b5dd6db41`
  * `division_uuid=5668ed34-5aa6-494d-808f-f5512ae89379`
  * `selected_date=YYYY-MM-DD` (varies per day)
* Pulls data for **today + next 4 days** (configurable).
* De‑dupes by `system_matchups.uuid` and sorts by `planned_start_date`.
* Emits **UTC** start/end times (your calendar renders them in local time).
* **Event title**: `Away vs. Home (Court)` — e.g., `Miami Pickleball Club vs. Texas Ranchers (Grandstand Court)`.
* **Court names** mapped (`GS → Grandstand Court`, `CC → Center Court`), unknown codes default to `"<code> Court"`.
* **DESCRIPTION** includes league + event group and, when available, **player names** for each team.
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
python make_mlp_ics_multi.py --output mlp.ics
```

Options:

* `--days 5` – number of days starting **today** (default 5)
* `--tz America/Los_Angeles` – timezone used to compute “today” (default `America/Los_Angeles`)
* `--url <base-url>` – override the base endpoint if needed
* `--output mlp.ics` – output file path

### Automation / Deploy (GitHub Pages + Actions)

Enable **Settings → Pages → Build and deployment = GitHub Actions** and use this workflow at `.github/workflows/build-ics.yml`:

```yaml
name: Build ICS hourly

on:
  schedule:
    - cron: "0 * * * *"   # hourly, on the hour (UTC)
  workflow_dispatch:       # manual run button

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps (if any)
        run: |
          python -m pip install --upgrade pip
          # pip install -r requirements.txt

      - name: Generate ICS
        run: |
          python make_mlp_ics_multi.py --output mlp.ics
          printf '<!doctype html><meta charset="utf-8"><title>MLP ICS</title><p><a href="mlp.ics">mlp.ics</a>' > index.html

      - name: Upload artifact for Pages
        uses: actions/upload-pages-artifact@v3
        with:
          path: .

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

### Manually trigger the workflow

* GitHub UI: **Actions → Build ICS hourly → Run workflow**.
* CLI:

```bash
gh workflow run "Build ICS hourly" --ref main
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
