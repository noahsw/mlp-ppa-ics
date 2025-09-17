# Overview

This project generates live-updating ICS calendar files for professional pickleball tournaments from Major League Pickleball (MLP) and Professional Pickleball Association (PPA). The system scrapes tournament schedules and matchup data from official websites, then creates standardized .ics calendar files that can be subscribed to by any calendar application. It supports multiple filtered calendar views (by court, division, tournament type) and provides both single-tournament and tour-wide calendar subscriptions.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Core Data Processing Architecture
The system uses a **web scraping and data transformation pipeline** to convert tournament data into standardized calendar formats. Two separate generators handle MLP and PPA data sources:

- **MLP Generator** (`make_mlp_ics_multi.py`): Fetches JSON data from MLP's REST API endpoints for matchup details and team information
- **PPA Generator** (`make_ppa_ics.py`): Scrapes HTML from PPA tournament pages using custom HTML parsers to extract schedule information

## ICS Calendar Generation
The system implements **RFC 5545 compliant ICS generation** through shared utilities in `ics_utils.py`. This handles:
- Special character escaping for ICS format requirements
- Line folding for long content according to RFC specifications
- Standardized calendar headers and structure

## Data Filtering and Multi-Calendar Support
The architecture supports **filtered calendar generation** to create specialized calendar feeds:
- Court-specific calendars (Championship Court, Grandstand Court)
- Division-specific calendars (Premier, Challenger for MLP)
- Category-specific calendars (Singles, Doubles, Championships for PPA)
- Broadcaster-specific calendars (PickleballTV, Tennis Channel)

## Error Handling and Resilience
The system implements **retry mechanisms and graceful degradation**:
- HTTP request retries with exponential backoff
- Fallback to local HTML files for testing
- Comprehensive error logging and debugging output
- Timezone handling with automatic conversion to UTC

## Testing Infrastructure
The project uses a **unittest-based testing framework** with separate test suites for each component:
- MLP data parsing and ICS generation tests
- PPA HTML parsing and schedule extraction tests
- ICS utility function validation tests
- Sample data files for consistent testing scenarios

# External Dependencies

## Data Sources
- **MLP API**: REST endpoints at majorleaguepickleball.co for live matchup and event data
- **PPA Website**: HTML scraping from ppatour.com tournament schedule pages

## Runtime Dependencies
- **Python Standard Library**: urllib, json, datetime, html.parser for core functionality
- **ZoneInfo** (Python 3.9+): Timezone handling with fallback for older Python versions
- **unittest**: Built-in testing framework for validation

## Output Format
- **ICS/iCalendar Standard**: RFC 5545 compliant calendar files for universal calendar application compatibility

## Development Tools
- **Sample Data Files**: JSON and HTML fixtures for testing without live API calls
- **Debug Modes**: Verbose logging and output for development and troubleshooting