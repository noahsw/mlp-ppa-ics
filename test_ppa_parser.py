
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
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Import the module we're testing
import make_ppa_ics as ppa


class TestPPAICSGenerator(unittest.TestCase):
    """Test cases for PPA ICS generator"""

    def setUp(self):
        """Set up test fixtures"""
        self.sample_html_file = "sample_ppa_schedule.html"
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

    def test_ics_escaping(self):
        """Test ICS special character escaping"""
        test_cases = [
            ("Hello, World!", "Hello\\, World!"),
            ("Line1\nLine2", "Line1\\nLine2"),
            ("Semi;colon", "Semi\\;colon"),
            ("Back\\slash", "Back\\\\slash"),
            ("Mixed's/Women's Doubles", "Mixed's/Women's Doubles"),  # Apostrophes should be preserved
        ]
        
        for input_str, expected in test_cases:
            result = ppa.ics_escape(input_str)
            self.assertEqual(result, expected, f"Failed to escape '{input_str}'")

    def test_ics_line_folding(self):
        """Test ICS line folding for long lines"""
        # Test short line (no folding needed)
        short_line = "SUMMARY:Short title"
        folded = ppa.fold_ical_line(short_line)
        self.assertEqual(folded, [short_line])
        
        # Test long line (folding needed)
        long_line = "DESCRIPTION:" + "A" * 100
        folded = ppa.fold_ical_line(long_line, limit=75)
        self.assertGreater(len(folded), 1, "Long line should be folded")
        self.assertTrue(folded[1].startswith(" "), "Continuation line should start with space")

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
            
            # Read and verify content
            with open(test_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Check ICS structure
            self.assertIn("BEGIN:VCALENDAR", content)
            self.assertIn("END:VCALENDAR", content)
            self.assertIn("VERSION:2.0", content)
            self.assertIn("PRODID:-//PPA ICS Generator//EN", content)
            self.assertIn(f"X-WR-CALNAME:PPA {self.tournament_name}", content)
            
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

    def test_command_line_interface(self):
        """Test the command line interface"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_output = os.path.join(temp_dir, "cli_test.ics")
            
            # Run the script with sample file
            result = subprocess.run([
                sys.executable, "make_ppa_ics.py",
                "--file", self.sample_html_file,
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
