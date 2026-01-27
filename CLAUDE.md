# CLAUDE.md - AI Assistant Guidelines

This document provides context for AI assistants working with the MLP-PPA-ICS codebase.

## Project Overview

This project generates live-updating iCalendar (ICS) files for professional pickleball tournaments from two organizations:
- **Major League Pickleball (MLP)** - fetches data from REST APIs
- **Professional Pickleball Association (PPA)** - scrapes HTML from tournament websites

Generated ICS files are published via GitHub Pages (hourly updates) for calendar subscription.

## Directory Structure

```
mlp-ppa-ics/
├── Core Modules:
│   ├── make_mlp_ics_multi.py    # MLP calendar generator (REST API → ICS)
│   ├── make_ppa_ics.py          # PPA calendar generator (HTML scraping → ICS)
│   └── ics_utils.py             # Shared ICS utilities (escaping, folding, headers)
│
├── Test Files:
│   ├── test_mlp_ics.py          # MLP test suite
│   ├── test_ppa_parser.py       # PPA test suite
│   ├── test_ics_utils.py        # ICS utilities tests
│   ├── run_tests.py             # Full test runner
│   └── run_ppa_tests.py         # PPA-specific test runner
│
├── Sample Data (for testing):
│   ├── sample_mlp_*.json        # MLP API response fixtures
│   └── sample_ppa_*.html        # PPA HTML page fixtures
│
├── Configuration:
│   ├── .github/workflows/build-ics.yml  # GitHub Actions (hourly)
│   ├── .gitignore               # Ignores *.ics files
│   └── .replit                  # Replit IDE config
│
└── Documentation:
    ├── README.md                # User-facing documentation
    └── replit.md                # Architecture documentation
```

## Technology Stack

- **Python 3.9+** (required for `zoneinfo` module)
- **Standard library only** - no external dependencies
- Key modules: `urllib`, `json`, `html.parser`, `zoneinfo`, `datetime`, `re`, `unittest`

## Quick Commands

### Running Generators

```bash
# MLP calendars (generates 7 ICS files)
python make_mlp_ics_multi.py --debug

# PPA calendars (generates 12+ ICS files)
python make_ppa_ics.py --debug

# MLP with custom options
python make_mlp_ics_multi.py --days 5 --tz America/Los_Angeles --debug
```

### Running Tests

```bash
# Run all tests
python run_tests.py

# Run PPA tests only
python run_ppa_tests.py

# Run specific test file
python -m unittest test_mlp_ics.py -v
python -m unittest test_ppa_parser.py -v

# Run with unittest directly
python -m unittest discover -v
```

## Code Conventions

### Python Style
- Use type hints for function signatures
- Include docstrings for modules and functions
- Follow PEP 8 naming conventions
- Use `#!/usr/bin/env python3` shebang

### ICS Generation
- Always use `ics_utils.py` functions for escaping and line folding
- All times must be converted to UTC before writing to ICS
- Use RFC 5545 compliant formatting
- CRLF line endings in ICS output (`\r\n`)

### Error Handling
- Use exponential backoff for HTTP retries (up to 4 attempts)
- Print warnings to stderr, not stdout
- Graceful degradation when data is missing
- Use `--debug` flag for verbose output

### Testing
- Use `unittest.TestCase` classes
- Descriptive test method names: `test_<feature>_<scenario>`
- Use sample JSON/HTML files for reproducible tests
- Test edge cases: empty data, None values, malformed input

## Key Data Flows

### MLP Pipeline
1. Fetch active tournaments from events API
2. For each tournament + division + date, fetch matchups
3. Dedupe by matchup UUID
4. Generate filtered ICS files (by division, court)

### PPA Pipeline
1. Scrape tournament schedule pages
2. Parse HTML with custom parser
3. Extract events with dates, times, courts, broadcasters
4. Convert Eastern Time to UTC
5. Generate filtered ICS files (by category, broadcaster, court)

## Output Files

### MLP (7 files)
- `mlp.ics` - All events
- `mlp-premier.ics`, `mlp-challenger.ics` - By division
- `mlp-{division}-{court}.ics` - By division and court

### PPA (12+ files)
- `ppa.ics` - All events
- `ppa-championships.ics`, `ppa-singles.ics`, `ppa-gender-doubles.ics`, `ppa-mixed-doubles.ics` - By category
- `ppa-{broadcaster}.ics` - By broadcaster (pickleballtv, tennis-channel, fs1, fs2, espn2)
- `ppa-{court}-court.ics` - By court

## Important Constants

### MLP Court Mapping (`make_mlp_ics_multi.py`)
```python
COURT_LABELS = {
    "GS": ("Grandstand Court", "grandstand"),
    "CC": ("Championship Court", "championship"),
}
```

### MLP Divisions
```python
DIVISIONS = {
    "Premier": "5668ed34-5aa6-494d-808f-f5512ae89379",
    "Challenger": "6fa08298-bfda-40c9-86bc-4e369aac8b77",
}
```

## Common Tasks

### Adding a New Broadcaster
1. Add broadcaster URL pattern detection in `make_ppa_ics.py`
2. Add new output file generation in `write_all_ics_files()`
3. Add test cases in `test_ppa_parser.py`
4. Update README.md with new subscription URL

### Adding a New Court Type
1. Update `COURT_LABELS` in `make_mlp_ics_multi.py`
2. Add new file generation logic
3. Add test cases
4. Update README.md

### Fixing Parsing Issues
1. Use `--debug` flag to see raw data
2. Check sample data files match current website structure
3. Update HTML parsing regex/logic as needed
4. Add new sample files for edge cases

## GitHub Actions

The workflow (`.github/workflows/build-ics.yml`) runs hourly:
1. Checkout code
2. Setup Python 3.11
3. Generate all ICS files with `--debug`
4. Create index.html
5. Deploy to GitHub Pages

## Guidelines for Changes

### Before Making Changes
- Run `python run_tests.py` to ensure tests pass
- Use `--debug` flag to understand current behavior
- Check existing sample data files for test fixtures

### When Adding Features
- Add corresponding test cases
- Update sample data files if needed
- Keep standard library only - no new dependencies
- Follow existing code patterns

### After Making Changes
- Run full test suite
- Test with `--debug` to verify output
- Update README.md if user-facing behavior changes

## External Data Sources

### MLP API Endpoints
- Events: `majorleaguepickleball.co/wp-json/fau-scores-and-stats/v1/event-matches`
- Matchups: `majorleaguepickleball.co/wp-json/fau-scores-and-stats/v1/single-event`

### PPA Website
- Tour schedule: `ppatour.com/schedule/`
- Tournament pages: `ppatour.com/tournament/{year}/{slug}/#schedule`

**Note:** These are unofficial data sources. Website structure changes may break parsing.

## Timezone Handling

- MLP API returns UTC timestamps
- PPA website uses Eastern Time (ET)
- All ICS output is in UTC
- Local timezone used only for date range calculations

## Debugging Tips

1. **No events generated:** Check API/website responses with `--debug`
2. **Parsing errors:** Compare sample files with current website structure
3. **Wrong times:** Check timezone conversion logic
4. **Missing data:** API may return empty for certain dates/tournaments
