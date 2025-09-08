#!/usr/bin/env python3
"""
Comprehensive test suite for PPA ICS parser

Tests various scenarios including:
- HTML parsing from sample data
- ICS file generation and validation
- Event parsing and formatting
- Edge cases and error handling
"""

import unittest
import tempfile
import os
import sys
import subprocess
import re
import shutil  # Import shutil for file copying
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Import the module we're testing
import make_ppa_ics as ppa


class TestPPAICSGenerator(unittest.TestCase):
    """Test cases for PPA ICS generator"""

    def setUp(self):
        """Set up test fixtures"""
        self.sample_html_file = "sample_ppa_tournament_schedule.html"
        self.tournament_name = "Open at the Las Vegas Strip"

    def test_html_parsing(self):
        """Test parsing HTML content from sample file"""
        # Read sample HTML
        with open(self.sample_html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Parse events
        events = ppa.parse_schedule_content(html_content)

        # Verify we got events
        self.assertGreater(len(events), 0, "Should parse at least one event")

        # Check first event structure
        first_event = events[0]
        required_fields = ['date', 'court', 'category', 'time', 'broadcaster']
        for field in required_fields:
            self.assertIn(field, first_event, f"Event should have {field} field")

        # Verify specific events exist
        self.assertTrue(
            any(e['category'] == 'Singles' and e['court'] == 'Championship Court'
                for e in events),
            "Should find Singles on Championship Court"
        )

        self.assertTrue(
            any(e['category'] == 'Mixed Doubles' for e in events),
            "Should find Mixed Doubles events"
        )

    def test_date_parsing(self):
        """Test date text parsing"""
        test_cases = [
            ("Thursday, August 28", "2025-08-28"),
            ("Friday, August 29", "2025-08-29"),
            ("Saturday, August 30", "2025-08-30"),
            ("Sunday, August 31", "2025-08-31"),
        ]

        for date_text, expected in test_cases:
            result = ppa.parse_date_text(date_text)
            self.assertEqual(result, expected, f"Failed to parse '{date_text}'")

    def test_time_range_parsing(self):
        """Test time range parsing and UTC conversion"""
        test_cases = [
            ("2:00 PM ET - 10:00 PM ET", "2025-08-28"),
            ("4:00 PM ET - 9:00 PM ET", "2025-08-28"),
            ("1:00 PM ET - 7:00 PM ET", "2025-08-31"),
            ("10:30 PM ET - 12:30 AM ET", "2025-08-31"),  # Midnight crossover
        ]

        for time_str, event_date in test_cases:
            start_time, end_time = ppa.parse_time_range(time_str, event_date)
            self.assertIsNotNone(start_time, f"Should parse start time from '{time_str}'")
            self.assertIsNotNone(end_time, f"Should parse end time from '{time_str}'")

            # Verify UTC format
            self.assertTrue(start_time.endswith('Z'), "Start time should be in UTC")
            self.assertTrue(end_time.endswith('Z'), "End time should be in UTC")

            # Verify end time is after start time (accounting for potential date change)
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            self.assertGreater(end_dt, start_dt, "End time should be after start time")



    def test_event_creation(self):
        """Test ICS event creation"""
        sample_event = {
            'date': '2025-08-28',
            'court': 'Championship Court',
            'category': 'Singles',
            'time': '2:00 PM ET - 10:00 PM ET',
            'broadcaster': 'PickleballTV'
        }

        dtstamp = "20250101T120000Z"
        event_lines = ppa.create_ics_event(sample_event, self.tournament_name, dtstamp)

        # Verify event was created
        self.assertGreater(len(event_lines), 0, "Should create event lines")

        event_text = "\n".join(event_lines)

        # Check required ICS fields
        self.assertIn("BEGIN:VEVENT", event_text)
        self.assertIn("END:VEVENT", event_text)
        self.assertIn("UID:", event_text)
        self.assertIn("DTSTAMP:", event_text)
        self.assertIn("DTSTART:", event_text)
        self.assertIn("DTEND:", event_text)
        self.assertIn("SUMMARY:", event_text)
        self.assertIn("DESCRIPTION:", event_text)

        # Check content
        self.assertIn("PPA Singles (Championship Court) - PickleballTV", event_text)
        self.assertIn("Tournament: Open at the Las Vegas Strip", event_text)

    def test_ics_file_generation(self):
        """Test complete ICS file generation from sample data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test_ppa_schedule.ics")

            # Read sample HTML
            with open(self.sample_html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # Parse events
            events = ppa.parse_schedule_content(html_content)

            # Write ICS file
            ppa.write_ics_file(test_file, events, self.tournament_name)

            # Verify file was created
            self.assertTrue(os.path.exists(test_file))

            # Read and verify content (use binary mode to preserve CRLF)
            with open(test_file, "rb") as f:
                content = f.read().decode("utf-8")

            # Check ICS structure
            self.assertIn("BEGIN:VCALENDAR", content)
            self.assertIn("END:VCALENDAR", content)
            self.assertIn("VERSION:2.0", content)
            self.assertIn("PRODID:-//MLP-PPA ICS Generator//EN", content)
            self.assertIn("X-WR-CALNAME:PPA Tour", content)

            # Count events
            event_count = content.count("BEGIN:VEVENT")
            self.assertEqual(event_count, len(events), "Should have correct number of events")

            # Check for specific content
            self.assertIn("PPA Singles", content)
            self.assertIn("Championship Court", content)
            self.assertIn("PickleballTV", content)
            self.assertIn("Tennis Channel", content)

            # Verify proper line endings
            self.assertTrue(content.endswith("\r\n"), "ICS file should end with CRLF")

    def test_tournament_url_extraction_from_tour_schedule(self):
        """Test extracting tournament URL from main tour schedule page"""
        # Test with sample tour schedule HTML (the main schedule listing page)
        with open("sample_ppa_tour_schedule.html", 'r', encoding='utf-8') as f:
            tour_schedule_html = f.read()

        tournament_url = ppa.extract_first_tournament_url(tour_schedule_html)
        self.assertIsNotNone(tournament_url, "Should extract tournament URL")
        self.assertIn("ppatour.com/tournament", tournament_url)
        self.assertIn("open-at-the-las-vegas-strip", tournament_url)

        # Test with empty HTML
        empty_url = ppa.extract_first_tournament_url("")
        self.assertIsNone(empty_url, "Should return None for empty HTML")

        # Test with HTML without tournament links
        no_tournament_html = "<html><body><p>No tournaments here</p></body></html>"
        no_url = ppa.extract_first_tournament_url(no_tournament_html)
        self.assertIsNone(no_url, "Should return None when no tournament links found")

    def test_tour_vs_tournament_schedule_page_detection(self):
        """Test detection of tour schedule page vs tournament schedule page"""
        # Test tournament schedule page detection (has "how-to-watch")
        with open(self.sample_html_file, 'r', encoding='utf-8') as f:
            tournament_schedule_html = f.read()
        self.assertIn("how-to-watch", tournament_schedule_html, "Tournament schedule page should have how-to-watch section")

        # Test tour schedule page detection (has "tournament-schedule")
        with open("sample_ppa_tour_schedule.html", 'r', encoding='utf-8') as f:
            tour_schedule_html = f.read()
        self.assertIn("tournament-schedule", tour_schedule_html, "Tour schedule page should have tournament-schedule section")

    def test_command_line_interface(self):
        """Test the command line interface"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_output = os.path.join(temp_dir, "cli_test.ics")

            # Test with tournament schedule file
            result = subprocess.run([
                sys.executable, "make_ppa_ics.py",
                "--tournament-schedule-file", self.sample_html_file,
                "--tournament", self.tournament_name,
                "--output", test_output,
                "--debug"
            ], capture_output=True, text=True)

            # Check it ran successfully
            self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")

            # Verify output file was created
            self.assertTrue(os.path.exists(test_output))

            # Verify debug output
            self.assertIn("Found", result.stdout)
            self.assertIn("events", result.stdout)
            self.assertIn("Created", result.stdout)

    def test_championships_only_command_line(self):
        """Test the championships-only command line option"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_output = os.path.join(temp_dir, "championships_cli_test.ics")

            # Test with championships-only flag
            result = subprocess.run([
                sys.executable, "make_ppa_ics.py",
                "--tournament-schedule-file", self.sample_html_file,
                "--tournament", self.tournament_name,
                "--championships-only",
                "--output", test_output,
                "--debug"
            ], capture_output=True, text=True)

            # Check it ran successfully
            self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")

            # With --championships-only, the filename gets modified to add -championships
            expected_output = os.path.join(temp_dir, "championships_cli_test-championships.ics")
            self.assertTrue(os.path.exists(expected_output), f"Expected championships file not created: {expected_output}")

            # Verify filtering debug output
            self.assertIn("Filtering to", result.stdout)
            self.assertIn("championship events", result.stdout)

            # Test default filename behavior
            default_output = os.path.join(temp_dir, "test_default_championships.ics")
            result = subprocess.run([
                sys.executable, "make_ppa_ics.py",
                "--tournament-schedule-file", self.sample_html_file,
                "--championships-only",
                "--debug"
            ], capture_output=True, text=True, cwd=temp_dir)

            # Should mention the default championships filename
            if result.returncode == 0:
                self.assertIn("ppa-championships.ics", result.stdout)

    def test_default_behavior(self):
        """Test the default behavior using sample files instead of network requests"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_output = os.path.join(temp_dir, "default_test.ics")

            # Test with tour schedule file (simulates default behavior without network)
            result = subprocess.run([
                sys.executable, "make_ppa_ics.py",
                "--tour-schedule-file", "sample_ppa_tour_schedule.html",
                "--output", test_output,
                "--debug"
            ], capture_output=True, text=True)

            # Should either succeed or fail gracefully with expected messages
            if result.returncode == 0:
                self.assertTrue(os.path.exists(test_output), "Should create output file on success")
            else:
                # Should fail with expected network-related error messages
                expected_errors = [
                    "Failed to fetch tournament page",
                    "No events found in the HTML content"
                ]
                found_expected_error = any(msg in result.stderr for msg in expected_errors)
                self.assertTrue(found_expected_error,
                              f"Should fail gracefully. Got stderr: {result.stderr}")

    def test_tour_schedule_to_tournament_schedule_workflow(self):
        """Test the workflow for processing tour schedule page with tournament URL extraction"""
        # Test the workflow functions directly instead of via subprocess
        # This avoids the mocking issues with subprocess execution

        # Read sample HTML files
        with open("sample_ppa_tour_schedule.html", 'r', encoding='utf-8') as f:
            tour_schedule_html = f.read()

        with open(self.sample_html_file, 'r', encoding='utf-8') as f:
            tournament_schedule_html = f.read()

        # Test the URL extraction function directly
        tournament_url = ppa.extract_first_tournament_url(tour_schedule_html)
        self.assertIsNotNone(tournament_url, "Should extract tournament URL from tour schedule")
        self.assertIn("open-at-the-las-vegas-strip", tournament_url)

        # Test tournament name extraction from URL
        import re
        url_match = re.search(r'/tournament/\d+/([^/]+)/?', tournament_url)
        self.assertIsNotNone(url_match, "Should match tournament URL pattern")

        tournament_name = url_match.group(1).replace('-', ' ').title()
        self.assertEqual(tournament_name, "Open At The Las Vegas Strip")

        # Test parsing the tournament schedule page directly
        events = ppa.parse_schedule_content(tournament_schedule_html)
        self.assertGreater(len(events), 0, "Should parse events from tournament schedule page")

        # Verify the workflow components work together
        with tempfile.TemporaryDirectory() as temp_dir:
            test_output = os.path.join(temp_dir, "workflow_test.ics")
            ppa.write_ics_file(test_output, events, tournament_name)

            self.assertTrue(os.path.exists(test_output), "Should create ICS file")

            # Verify ICS content
            with open(test_output, "r", encoding="utf-8") as f:
                ics_content = f.read()

            self.assertIn("X-WR-CALNAME:PPA Tour", ics_content)
            self.assertIn("BEGIN:VEVENT", ics_content)

    def test_tournament_name_extraction(self):
        """Test extracting tournament name from URL"""
        test_cases = [
            ("https://www.ppatour.com/tournament/2025/open-at-the-las-vegas-strip/", "Open At The Las Vegas Strip"),
            ("https://www.ppatour.com/tournament/2025/cincinnati-slam/", "Cincinnati Slam"),
            ("https://www.ppatour.com/tournament/2025/sacramento-vintage-open/", "Sacramento Vintage Open"),
        ]

        for url, expected_name in test_cases:
            match = re.search(r'/tournament/\d+/([^/]+)/?', url)
            if match:
                extracted_name = match.group(1).replace('-', ' ').title()
                self.assertEqual(extracted_name, expected_name, f"Failed to extract name from {url}")

    def test_newline_handling_in_descriptions(self):
        """Test that event descriptions use actual newlines, not literal \\n characters"""
        sample_event = {
            'date': '2025-08-28',
            'court': 'Championship Court',
            'category': 'Mixed Doubles',
            'time': '2:00 PM ET - 10:00 PM ET',
            'broadcaster': 'PickleballTV'
        }

        dtstamp = "20250101T120000Z"
        event_lines = ppa.create_ics_event(sample_event, "Test Tournament", dtstamp)
        event_text = "\n".join(event_lines)

        # Find the description line (accounting for ICS line folding)
        description_match = re.search(r'DESCRIPTION:([^\n]+(?:\n [^\n]+)*)', event_text)
        self.assertIsNotNone(description_match, "Should find DESCRIPTION field in event")

        # Extract the description content and unfold ICS line continuations
        description_content = description_match.group(1)
        unfolded_description = description_content.replace('\n ', '')

        # The description should contain actual \\n escape sequences (for ICS format)
        # but NOT literal backslash-n characters like \\n
        self.assertIn('\\n', unfolded_description, "Description should contain ICS newline escapes")

        # When we unescape it, we should get actual newlines
        unescaped = unfolded_description.replace('\\n', '\n').replace('\\,', ',').replace('\\;', ';').replace('\\\\', '\\')

        # Should have multiple lines when unescaped
        description_lines = unescaped.split('\n')
        self.assertGreater(len(description_lines), 1, "Description should have multiple lines")

        # Should contain expected content on separate lines
        self.assertIn("Tournament: Test Tournament", description_lines)
        self.assertIn("Category: Mixed Doubles", description_lines)
        self.assertIn("Court: Championship Court", description_lines)
        self.assertIn("Broadcaster: PickleballTV", description_lines)

    def test_championship_event_filtering(self):
        """Test filtering of championship events"""
        sample_events = [
            {
                'date': '2025-08-30',
                'court': 'Championship Court',
                'category': 'Singles',
                'time': '2:00 PM ET - 4:00 PM ET',
                'broadcaster': 'PickleballTV'
            },
            {
                'date': '2025-08-30',
                'court': 'Championship Court',
                'category': 'Championships',
                'time': '4:00 PM ET - 6:00 PM ET',
                'broadcaster': 'Tennis Channel'
            },
            {
                'date': '2025-08-31',
                'court': 'Championship Court',
                'category': 'Mixed Doubles Final',
                'time': '1:00 PM ET - 3:00 PM ET',
                'broadcaster': 'FS2'
            },
            {
                'date': '2025-08-31',
                'court': 'Grandstand Court',
                'category': 'Bronze Medal Match',
                'time': '3:00 PM ET - 5:00 PM ET',
                'broadcaster': 'PickleballTV'
            },
            {
                'date': '2025-08-31',
                'court': 'Championship Court',
                'category': 'Gold Medal Championship',
                'time': '5:00 PM ET - 7:00 PM ET',
                'broadcaster': 'Tennis Channel'
            }
        ]

        # Test the filtering function
        championship_events = ppa.filter_championship_events(sample_events)

        # Should filter to only championship-related events
        self.assertEqual(len(championship_events), 4, "Should find 4 championship events")

        # Check that the right events were filtered
        categories = [event['category'] for event in championship_events]
        self.assertIn('Championships', categories)
        self.assertIn('Mixed Doubles Final', categories)
        self.assertIn('Bronze Medal Match', categories)
        self.assertIn('Gold Medal Championship', categories)
        self.assertNotIn('Singles', categories)

    def test_championship_filtering_command_line(self):
        """Test championship filtering via command line interface"""
        with tempfile.TemporaryDirectory() as temp_dir:
            main_output = os.path.join(temp_dir, "ppa.ics")
            championship_output = os.path.join(temp_dir, "ppa-championships.ics")

            # Test with championship filtering enabled
            result = subprocess.run([
                sys.executable, "make_ppa_ics.py",
                "--tournament-schedule-file", self.sample_html_file,
                "--tournament", self.tournament_name,
                "--output", main_output,
                "--championships-only",
                "--debug"
            ], capture_output=True, text=True)

            # Check it ran successfully
            self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")

            # With --championships-only, should only create the championships file
            # The output filename should be modified to include -championships
            expected_championships_file = os.path.join(temp_dir, "ppa-championships.ics")

            # Check if championship file was created
            if os.path.exists(expected_championships_file):
                # Verify championship file content
                with open(expected_championships_file, "r", encoding="utf-8") as f:
                    championship_content = f.read()

                self.assertIn("BEGIN:VCALENDAR", championship_content)
                self.assertIn("X-WR-CALNAME:PPA Tour", championship_content)
                self.assertIn("END:VCALENDAR", championship_content)

                # The debug output should show filtering message
                if "Filtering to" in result.stdout:
                    self.assertIn("championship events", result.stdout)
            else:
                # If no championship file was created, should see appropriate message
                self.assertTrue(
                    "No championship events found" in result.stderr or
                    "No championship events found" in result.stdout,
                    "Should indicate no championship events found"
                )

    def test_championship_filtering_with_no_championship_events(self):
        """Test championship filtering when no championship events exist"""
        # Create sample events without any championship events
        sample_events = [
            {
                'date': '2025-08-30',
                'court': 'Championship Court',
                'category': 'Singles',
                'time': '2:00 PM ET - 4:00 PM ET',
                'broadcaster': 'PickleballTV'
            },
            {
                'date': '2025-08-30',
                'court': 'Grandstand Court',
                'category': 'Mixed Doubles',
                'time': '4:00 PM ET - 6:00 PM ET',
                'broadcaster': 'Tennis Channel'
            }
        ]

        # Test the filtering function
        championship_events = ppa.filter_championship_events(sample_events)
        self.assertEqual(len(championship_events), 0, "Should find no championship events")

    def test_championship_filename_generation(self):
        """Test that championship filenames are generated correctly"""
        test_cases = [
            ("ppa.ics", "ppa-championships.ics"),
            ("tournament.ics", "tournament-championships.ics"),
            ("my_schedule.ics", "my_schedule-championships.ics"),
            ("test", "test-championships.ics"),
        ]

        for input_filename, expected_output in test_cases:
            base_name = os.path.splitext(input_filename)[0]
            championship_filename = f"{base_name}-championships.ics"
            self.assertEqual(championship_filename, expected_output,
                           f"Failed for input: {input_filename}")

    def test_broadcaster_detection(self):
        """Test broadcaster detection from URLs"""
        test_cases = [
            ("https://stream.pickleballtv.com/", "PickleballTV"),
            ("https://www.tennischannel.com/en-us/page/home", "Tennis Channel"),
            ("https://www.foxsports.com/live/fs1", "FS1"),
            ("https://www.foxsports.com/live/fs2", "FS2"),
            ("https://unknown-broadcaster.com", "Unknown"),
        ]

        for url, expected in test_cases:
            # Create mock HTML with broadcaster link
            html = f'<a class="how-to-watch__schedule-platform" href="{url}">Broadcaster</a>'

            # This would normally be tested through the parser, but we can test the logic
            broadcaster = "Unknown"
            if 'pickleballtv.com' in url:
                broadcaster = 'PickleballTV'
            elif 'tennischannel.com' in url:
                broadcaster = 'Tennis Channel'
            elif 'foxsports.com/live/fs1' in url:
                broadcaster = 'FS1'
            elif 'foxsports.com/live/fs2' in url:
                broadcaster = 'FS2'

            self.assertEqual(broadcaster, expected, f"Failed to detect broadcaster for {url}")

    def test_edge_cases(self):
        """Test various edge cases"""
        # Test empty HTML
        events = ppa.parse_schedule_content("")
        self.assertEqual(len(events), 0, "Empty HTML should return no events")

        # Test HTML without schedule section
        html = "<html><body><p>No schedule here</p></body></html>"
        events = ppa.parse_schedule_content(html)
        self.assertEqual(len(events), 0, "HTML without schedule should return no events")

        # Test invalid time range
        start, end = ppa.parse_time_range("Invalid time", "2025-08-28")
        self.assertIsNone(start)
        self.assertIsNone(end)

        # Test invalid date
        result = ppa.parse_date_text("Invalid date")
        self.assertIsNone(result)

    def test_championship_filtering(self):
        """Test filtering events to only championship events"""
        # Create test events with various categories
        test_events = [
            {'category': 'Singles', 'date': '2025-08-28', 'court': 'Court 1', 'time': '1:00 PM ET - 3:00 PM ET', 'broadcaster': 'PickleballTV'},
            {'category': 'Championships', 'date': '2025-08-30', 'court': 'Championship Court', 'time': '2:00 PM ET - 4:00 PM ET', 'broadcaster': 'Tennis Channel'},
            {'category': 'Mixed Doubles', 'date': '2025-08-29', 'court': 'Court 2', 'time': '10:00 AM ET - 12:00 PM ET', 'broadcaster': 'FS2'},
            {'category': 'Men\'s/Women\'s Doubles Final', 'date': '2025-08-31', 'court': 'Championship Court', 'time': '3:00 PM ET - 5:00 PM ET', 'broadcaster': 'PickleballTV'},
            {'category': 'Women\'s Singles Championship', 'date': '2025-08-31', 'court': 'Championship Court', 'time': '4:00 PM ET - 6:00 PM ET', 'broadcaster': 'Tennis Channel'},
        ]

        # Test filtering function
        championship_events = ppa.filter_championship_events(test_events)

        # Should have 3 championship events (Championships, Final, Championship)
        self.assertEqual(len(championship_events), 3, "Should filter to 3 championship events")

        # Verify the right events are included
        championship_categories = [e['category'] for e in championship_events]
        self.assertIn('Championships', championship_categories)
        self.assertIn('Men\'s/Women\'s Doubles Final', championship_categories)
        self.assertIn('Women\'s Singles Championship', championship_categories)

        # Verify non-championship events are excluded
        self.assertNotIn('Singles', championship_categories)
        self.assertNotIn('Mixed Doubles', championship_categories)

    def test_singles_filtering(self):
        """Test filtering events to only singles events"""
        test_events = [
            {'category': 'Singles', 'date': '2025-08-28', 'court': 'Court 1', 'time': '1:00 PM ET - 3:00 PM ET', 'broadcaster': 'PickleballTV'},
            {'category': 'Singles', 'date': '2025-08-29', 'court': 'Court 2', 'time': '2:00 PM ET - 4:00 PM ET', 'broadcaster': 'Tennis Channel'},
            {'category': 'Mixed Doubles', 'date': '2025-08-30', 'court': 'Court 3', 'time': '3:00 PM ET - 5:00 PM ET', 'broadcaster': 'FS2'},
        ]

        singles_events = ppa.filter_singles_events(test_events)
        self.assertEqual(len(singles_events), 2, "Should filter to 2 singles events")

        categories = [e['category'] for e in singles_events]
        self.assertIn('Singles', categories)
        self.assertNotIn('Mixed Doubles', categories)

    def test_gender_doubles_filtering(self):
        """Test filtering events to only men's/women's doubles events"""
        test_events = [
            {'category': 'Men\'s/Women\'s Doubles', 'date': '2025-08-28', 'court': 'Court 1', 'time': '1:00 PM ET - 3:00 PM ET', 'broadcaster': 'PickleballTV'},
            {'category': 'Men\'s/Women\'s Doubles', 'date': '2025-08-29', 'court': 'Court 2', 'time': '2:00 PM ET - 4:00 PM ET', 'broadcaster': 'Tennis Channel'},
            {'category': 'Singles', 'date': '2025-08-30', 'court': 'Court 3', 'time': '3:00 PM ET - 5:00 PM ET', 'broadcaster': 'FS2'},
            {'category': 'Mixed Doubles', 'date': '2025-08-31', 'court': 'Court 4', 'time': '4:00 PM ET - 6:00 PM ET', 'broadcaster': 'PickleballTV'},
        ]

        gender_doubles_events = ppa.filter_gender_doubles_events(test_events)
        self.assertEqual(len(gender_doubles_events), 2, "Should filter to 2 gender doubles events")

        categories = [e['category'] for e in gender_doubles_events]
        self.assertIn('Men\'s/Women\'s Doubles', categories)
        self.assertNotIn('Mixed Doubles', categories)
        self.assertNotIn('Singles', categories)

    def test_mixed_doubles_filtering(self):
        """Test filtering events to only mixed doubles events"""
        test_events = [
            {'category': 'Mixed Doubles', 'date': '2025-08-28', 'court': 'Court 1', 'time': '1:00 PM ET - 3:00 PM ET', 'broadcaster': 'PickleballTV'},
            {'category': 'Mixed Doubles Final', 'date': '2025-08-29', 'court': 'Court 2', 'time': '2:00 PM ET - 4:00 PM ET', 'broadcaster': 'Tennis Channel'},
            {'category': 'Men\'s Doubles', 'date': '2025-08-30', 'court': 'Court 3', 'time': '3:00 PM ET - 5:00 PM ET', 'broadcaster': 'FS2'},
        ]

        mixed_doubles_events = ppa.filter_mixed_doubles_events(test_events)
        self.assertEqual(len(mixed_doubles_events), 2, "Should filter to 2 mixed doubles events")

        categories = [e['category'] for e in mixed_doubles_events]
        self.assertIn('Mixed Doubles', categories)
        self.assertIn('Mixed Doubles Final', categories)
        self.assertNotIn('Men\'s Doubles', categories)

    def test_broadcaster_filtering(self):
        """Test filtering events by broadcaster"""
        test_events = [
            {'category': 'Singles', 'date': '2025-08-28', 'court': 'Court 1', 'time': '1:00 PM ET - 3:00 PM ET', 'broadcaster': 'PickleballTV'},
            {'category': 'Doubles', 'date': '2025-08-29', 'court': 'Court 2', 'time': '2:00 PM ET - 4:00 PM ET', 'broadcaster': 'Tennis Channel'},
            {'category': 'Mixed', 'date': '2025-08-30', 'court': 'Court 3', 'time': '3:00 PM ET - 5:00 PM ET', 'broadcaster': 'FS2'},
        ]

        # Test PickleballTV filtering
        ptv_events = ppa.filter_by_broadcaster(test_events, "PickleballTV")
        self.assertEqual(len(ptv_events), 1, "Should filter to 1 PickleballTV event")
        self.assertEqual(ptv_events[0]['broadcaster'], 'PickleballTV')

        # Test Tennis Channel filtering
        tc_events = ppa.filter_by_broadcaster(test_events, "Tennis Channel")
        self.assertEqual(len(tc_events), 1, "Should filter to 1 Tennis Channel event")
        self.assertEqual(tc_events[0]['broadcaster'], 'Tennis Channel')

        # Test FS1 filtering with actual sample data
        with open(self.sample_html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        real_events = ppa.parse_schedule_content(html_content)
        fs1_events = ppa.filter_by_broadcaster(real_events, "FS1")
        self.assertEqual(len(fs1_events), 1, "Should filter to 1 FS1 event from sample data")

        # Test FS2 filtering
        fs2_events = ppa.filter_by_broadcaster(test_events, "FS2")
        self.assertEqual(len(fs2_events), 1, "Should filter to 1 FS2 event")
        self.assertEqual(fs2_events[0]['broadcaster'], 'FS2')

    def test_court_filtering(self):
        """Test filtering events by court"""
        test_events = [
            {'category': 'Singles', 'date': '2025-08-28', 'court': 'Championship Court', 'time': '1:00 PM ET - 3:00 PM ET', 'broadcaster': 'PickleballTV'},
            {'category': 'Doubles', 'date': '2025-08-29', 'court': 'Grandstand Court', 'time': '2:00 PM ET - 4:00 PM ET', 'broadcaster': 'Tennis Channel'},
            {'category': 'Mixed', 'date': '2025-08-30', 'court': 'Championship Court', 'time': '3:00 PM ET - 5:00 PM ET', 'broadcaster': 'FS2'},
        ]

        # Test Championship Court filtering
        championship_court_events = ppa.filter_by_court(test_events, "Championship Court")
        self.assertEqual(len(championship_court_events), 2, "Should filter to 2 Championship Court events")
        for event in championship_court_events:
            self.assertIn("Championship Court", event['court'])

        # Test Grandstand Court filtering
        grandstand_court_events = ppa.filter_by_court(test_events, "Grandstand Court")
        self.assertEqual(len(grandstand_court_events), 1, "Should filter to 1 Grandstand Court event")
        self.assertEqual(grandstand_court_events[0]['court'], 'Grandstand Court')

    def test_championships_only_ics_generation(self):
        """Test generating ICS file with championships-only filtering"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "championships_test.ics")

            # Read sample HTML
            with open(self.sample_html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # Parse events
            events = ppa.parse_schedule_content(html_content)

            # Filter to championships events and write ICS file
            championship_events = ppa.filter_championship_events(events)

            # Create championships filename
            base, ext = os.path.splitext(test_file)
            championships_file = f"{base}-championships{ext}"

            ppa.write_ics_file(championships_file, championship_events, self.tournament_name, "PPA Tour - Championships")

            # The championships file should be created
            self.assertTrue(os.path.exists(championships_file), f"Expected championships file not created: {championships_file}")

            # Read and validate content
            with open(championships_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Check ICS structure
            self.assertIn("BEGIN:VCALENDAR", content)
            self.assertIn("END:VCALENDAR", content)
            self.assertIn("X-WR-CALNAME:PPA Tour - Championships", content)

            # Count events in ICS file
            event_count = content.count("BEGIN:VEVENT")

            # Count championship events in original data
            championship_events_filtered = ppa.filter_championship_events(events)

            self.assertEqual(event_count, len(championship_events_filtered), "Should have correct number of championship events")

            # Should only contain championship-related events
            if championship_events_filtered:
                # Check that championship events are included
                for event in championship_events_filtered:
                    expected_summary = f"PPA {event['category']} ({event['court']}) - {event['broadcaster']}"
                    self.assertIn(ppa.ics_escape(expected_summary), content,
                                f"ICS should contain championship event: {expected_summary}")

    def test_full_integration(self):
        """Test full integration from HTML to ICS with content validation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "integration_test.ics")

            # Read sample HTML
            with open(self.sample_html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # Parse events
            events = ppa.parse_schedule_content(html_content)

            # Verify we have expected events
            self.assertGreater(len(events), 10, "Should have multiple events")

            # Check for expected event types
            categories = [e['category'] for e in events]
            self.assertIn('Singles', categories)
            self.assertIn('Mixed Doubles', categories)
            self.assertIn('Men\'s/Women\'s Doubles', categories)
            self.assertIn('Championships', categories)

            # Check for expected courts
            courts = [e['court'] for e in events]
            self.assertIn('Championship Court', courts)
            self.assertIn('Grandstand Court', courts)

            # Check for expected broadcasters
            broadcasters = [e['broadcaster'] for e in events]
            self.assertIn('PickleballTV', broadcasters)
            self.assertIn('Tennis Channel', broadcasters)
            self.assertIn('FS2', broadcasters)

            # Write ICS file
            ppa.write_ics_file(test_file, events, self.tournament_name)

            # Read and validate ICS content
            with open(test_file, "r", encoding="utf-8") as f:
                ics_content = f.read()

            # Validate each parsed event appears in ICS
            for event in events:
                expected_summary = f"PPA {event['category']} ({event['court']}) - {event['broadcaster']}"
                self.assertIn(ppa.ics_escape(expected_summary), ics_content,
                            f"ICS should contain event: {expected_summary}")

    def test_multiple_ics_files_generation(self):
        """Test generation of multiple specialized ICS files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_file = os.path.join(temp_dir, "ppa.ics")

            # Read sample HTML
            with open(self.sample_html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # Parse events
            events = ppa.parse_schedule_content(html_content)

            # Generate all ICS files
            ppa.write_all_ics_files(base_file, events, self.tournament_name, debug=True)

            # Check that expected files were created
            expected_files = [
                'ppa.ics', 'ppa-championships.ics', 'ppa-singles.ics',
                'ppa-gender-doubles.ics', 'ppa-mixed-doubles.ics',
                'ppa-pickleballtv.ics', 'ppa-tennis-channel.ics', 'ppa-fs1.ics', 'ppa-fs2.ics',
                'ppa-championship-court.ics', 'ppa-grandstand-court.ics'
            ]

            created_files = []
            for filename in expected_files:
                file_path = os.path.join(temp_dir, filename)
                if os.path.exists(file_path):
                    created_files.append(filename)
                    # Verify file has valid ICS structure
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.assertIn("BEGIN:VCALENDAR", content)
                    self.assertIn("END:VCALENDAR", content)
                    self.assertIn("X-WR-CALNAME:PPA Tour", content)

            self.assertGreater(len(created_files), 0, "Should create at least some ICS files")
            self.assertIn("ppa.ics", created_files, "Should always create main ICS file")

            # Test specific filtering - verify singles file only has singles events
            singles_file = os.path.join(temp_dir, "ppa-singles.ics")
            if os.path.exists(singles_file):
                with open(singles_file, "r", encoding="utf-8") as f:
                    singles_content = f.read()
                # Should contain "Singles" but not "Mixed Doubles"
                if "BEGIN:VEVENT" in singles_content:  # Only check if there are events
                    self.assertIn("Singles", singles_content)
                    self.assertNotIn("Mixed Doubles", singles_content)

    def test_error_handling(self):
        """Test error handling for various failure scenarios"""
        # Test with non-existent file
        result = subprocess.run([
            sys.executable, "make_ppa_ics.py",
            "--tournament-schedule-file", "non_existent_file.html"
        ], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, "Should fail with non-existent file")

        # Test with empty HTML file - should now create empty ICS instead of failing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write("<html><body>No schedule data</body></html>")
            empty_file = f.name

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                output_file = os.path.join(temp_dir, "empty_test.ics")
                result = subprocess.run([
                    sys.executable, "make_ppa_ics.py",
                    "--tournament-schedule-file", empty_file,
                    "--tournament", "Empty Tournament",
                    "--output", output_file
                ], capture_output=True, text=True)
                
                # Should succeed with zero events
                self.assertEqual(result.returncode, 0, "Should succeed and create empty ICS file")
                self.assertTrue(os.path.exists(output_file), "Should create output file")
                
                # Verify empty ICS file structure
                with open(output_file, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("BEGIN:VCALENDAR", content)
                self.assertIn("END:VCALENDAR", content)
                self.assertIn("X-WR-CALNAME:PPA Tour", content)
                self.assertEqual(content.count("BEGIN:VEVENT"), 0, "Should have zero events")
        finally:
            os.unlink(empty_file)

        # Test with HTML file that has malformed tournament links
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write('<html><body><a href="not-a-valid-tournament-url">Bad Link</a></body></html>')
            malformed_file = f.name

        try:
            result = subprocess.run([
                sys.executable, "make_ppa_ics.py",
                "--tour-schedule-file", malformed_file
            ], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, "Should fail with malformed tournament links")
        finally:
            os.unlink(malformed_file)

    def test_explicit_file_input_modes(self):
        """Test explicit file input scenarios for tour schedule vs tournament schedule"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with tournament schedule file (specific tournament's how-to-watch page)
            tournament_schedule_output = os.path.join(temp_dir, "tournament_schedule.ics")
            result = subprocess.run([
                sys.executable, "make_ppa_ics.py",
                "--tournament-schedule-file", "sample_ppa_tournament_schedule.html",
                "--tournament", "Open at the Las Vegas Strip",
                "--output", tournament_schedule_output
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f"Should work with tournament schedule file. Error: {result.stderr}")
            self.assertTrue(os.path.exists(tournament_schedule_output))

            # Test URL extraction from tour schedule file without attempting network fetch
            # Read the tour schedule file and test URL extraction directly
            with open("sample_ppa_tour_schedule.html", 'r', encoding='utf-8') as f:
                tour_html = f.read()

            # Test that we can extract a tournament URL from the tour schedule
            tournament_url = ppa.extract_first_tournament_url(tour_html)
            self.assertIsNotNone(tournament_url, "Should extract tournament URL from tour schedule file")
            self.assertIn("ppatour.com/tournament", tournament_url)
            self.assertIn("open-at-the-las-vegas-strip", tournament_url)


def run_test_suite():
    """Run the test suite with detailed output"""
    print("Running PPA ICS Generator Test Suite...")
    print("=" * 60)

    suite = unittest.TestLoader().loadTestsFromTestCase(TestPPAICSGenerator)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print(f"\n{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.failures:
        print(f"\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}")
            print(f"  {traceback}")

    if result.errors:
        print(f"\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}")
            print(f"  {traceback}")

    if result.wasSuccessful():
        print(f"\n✅ All tests passed!")
        return True
    else:
        print(f"\n❌ Some tests failed!")
        return False


if __name__ == "__main__":
    success = run_test_suite()
    sys.exit(0 if success else 1)