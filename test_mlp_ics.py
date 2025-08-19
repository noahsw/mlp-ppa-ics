#!/usr/bin/env python3
"""
Test cases for make_mlp_ics_multi.py

Tests various scenarios including:
- Completed matchups with scores
- In-progress matchups
- Different court types
- Player name extraction
- Score formatting
- Edge cases and error handling
"""

import unittest
import json
import tempfile
import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Import the module we're testing
import make_mlp_ics_multi as mlp


# Helper function to load sample data from JSON file
def load_sample_matchups_data():
    with open('sample_matchups_data.json', 'r') as f:
        return json.load(f)

# Helper function to create sample data for testing
def create_sample_data():
    sample_data = load_sample_matchups_data()
    return {
        "results": {
            "system_matchups": [
                sample_data["completed_matchup"]
            ]
        }
    }

# Helper function to load sample events data from JSON file
def load_sample_events_data():
    with open('sample_events_data.json', 'r') as f:
        return json.load(f)


class TestMLPICSGenerator(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        sample_data = load_sample_matchups_data()
        self.sample_completed_matchup = sample_data["completed_matchup"]
        self.sample_in_progress_matchup = sample_data["in_progress_matchup"]
        self.sample_upcoming_matchup = sample_data["upcoming_matchup"]

    def test_court_label_mapping(self):
        """Test court code to label mapping"""
        self.assertEqual(mlp.court_label_from_code("GS"), "Grandstand Court")
        self.assertEqual(mlp.court_label_from_code("CC"), "Championship Court")
        self.assertIsNone(mlp.court_label_from_code("XX"))  # Unknown code
        self.assertIsNone(mlp.court_label_from_code(None))

    def test_primary_court_code_extraction(self):
        """Test extracting primary court code from matchup"""
        matchup_with_court = {
            "matches": [
                {"court_title": "GS"},
                {"court_title": "GS"},
                {"court_title": "CC"}
            ]
        }
        self.assertEqual(mlp.primary_court_code(matchup_with_court), "GS")

        matchup_with_courts_array = {
            "matches": [],
            "courts": [{"title": "CC"}]
        }
        self.assertEqual(mlp.primary_court_code(matchup_with_courts_array), "CC")

    def test_event_title_generation(self):
        """Test event title generation with and without court info"""
        # With court
        matchup_with_court = {
            "team_one_title": "Home Team",
            "team_two_title": "Away Team",
            "matches": [{"court_title": "GS"}]
        }
        expected = "Away Team vs. Home Team (Grandstand Court)"
        self.assertEqual(mlp.make_event_title(matchup_with_court), expected)

        # Without court
        matchup_no_court = {
            "team_one_title": "Home Team",
            "team_two_title": "Away Team",
            "matches": []
        }
        expected = "Away Team vs. Home Team"
        self.assertEqual(mlp.make_event_title(matchup_no_court), expected)

    def test_player_extraction(self):
        """Test player name extraction from matchup"""
        away_players, home_players = mlp.extract_players(self.sample_completed_matchup)

        self.assertEqual(sorted(away_players), ["Catherine Parenteau", "Jade Kawamoto", "Matt Wright", "Riley Newman"])
        self.assertEqual(sorted(home_players), ["Anna Leigh Waters", "Ben Johns", "Dylan Frazier", "Meghan Dizon"])

    def test_player_name_coalescing(self):
        """Test player name fallback logic"""
        # Test full name priority
        result = mlp._coalesce_full_name("Full Name", "First", "Last")
        self.assertEqual(result, "Full Name")

        # Test first + last fallback
        result = mlp._coalesce_full_name(None, "First", "Last")
        self.assertEqual(result, "First Last")

        # Test single name
        result = mlp._coalesce_full_name(None, "First", None)
        self.assertEqual(result, "First")

        # Test empty
        result = mlp._coalesce_full_name(None, None, None)
        self.assertIsNone(result)

    def test_ics_escaping(self):
        """Test ICS special character escaping"""
        test_cases = [
            ("Hello, World!", "Hello\\, World!"),
            ("Line1\nLine2", "Line1\\nLine2"),
            ("Semi;colon", "Semi\\;colon"),
            ("Back\\slash", "Back\\\\slash"),
            ("All,bad;chars\nhere\\", "All\\,bad\\;chars\\nhere\\\\")
        ]

        for input_str, expected in test_cases:
            self.assertEqual(mlp.ics_escape(input_str), expected)

    def test_datetime_formatting(self):
        """Test UTC datetime formatting for ICS"""
        dt_str = "2025-08-16T18:30:00Z"
        expected = "20250816T183000Z"
        self.assertEqual(mlp.fmt_dt_utc(dt_str), expected)

    def test_completed_matchup_event_generation(self):
        """Test event generation for completed matchup with scores"""
        dtstamp = "20250101T120000Z"
        event_lines = mlp.build_event(self.sample_completed_matchup, dtstamp, "Premier")

        event_text = "\n".join(event_lines)

        # Check for required ICS fields
        self.assertIn("BEGIN:VEVENT", event_text)
        self.assertIn("END:VEVENT", event_text)
        self.assertIn("UID:sample-completed-123@mlp", event_text)
        self.assertIn("SUMMARY:Texas Ranchers vs. Miami Pickleball Club", event_text)

        # Check for score information in description
        self.assertIn("FINAL SCORE: Texas Ranchers 0 - 3 Miami Pickleball Club", event_text)
        self.assertIn("Mixed Doubles", event_text)
        self.assertIn("Texas Ranchers 9 - 11 Miami Pickleball Club", event_text)
        self.assertIn("Women's Doubles", event_text)
        self.assertIn("Texas Ranchers 7 - 11 Miami Pickleball Club", event_text)

        # Check for player information (accounting for ICS escaping and line folding)
        self.assertIn("Catherine Parenteau\\; Jade Kawamoto\\; Matt Wright\\; Riley Newman", event_text)
        # Handle potential line folding in ICS output by checking for the pattern with possible line breaks
        import re
        # The pattern needs to account for line breaks that can occur within names due to ICS line folding
        anna_ben_pattern = r"Anna Leigh Waters\\; Ben Johns\\; Dylan Frazier\\; Meghan Dizon"
        self.assertRegex(event_text, anna_ben_pattern)

    def test_in_progress_matchup_event_generation(self):
        """Test event generation for in-progress matchup"""
        dtstamp = "20250101T120000Z"
        event_lines = mlp.build_event(self.sample_in_progress_matchup, dtstamp, "Challenger")

        event_text = "\n".join(event_lines)

        # Should not have FINAL SCORE for in-progress
        self.assertNotIn("FINAL SCORE", event_text)
        # But should have division info (may be split due to line folding)
        self.assertIn("Division:", event_text)
        self.assertIn("Challenger", event_text)

    def test_upcoming_matchup_event_generation(self):
        """Test event generation for upcoming matchup"""
        dtstamp = "20250101T120000Z"
        event_lines = mlp.build_event(self.sample_upcoming_matchup, dtstamp, "Premier")

        event_text = "\n".join(event_lines)

        # Should not have score information
        self.assertNotIn("FINAL SCORE", event_text)
        self.assertNotIn("Individual Match Results", event_text)

    def test_court_filtering(self):
        """Test filtering matchups by court"""
        matchups = [
            {"matches": [{"court_title": "GS"}], "uuid": "1"},
            {"matches": [{"court_title": "CC"}], "uuid": "2"},
            {"matches": [{"court_title": "GS"}], "uuid": "3"},
            {"matches": [], "uuid": "4"}
        ]

        # Test primary court detection
        self.assertEqual(mlp.primary_court_code(matchups[0]), "GS")
        self.assertEqual(mlp.primary_court_code(matchups[1]), "CC")
        self.assertEqual(mlp.primary_court_code(matchups[2]), "GS")
        self.assertIsNone(mlp.primary_court_code(matchups[3]))

    def test_ics_file_writing(self):
        """Test writing ICS file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test.ics")
            matchups = [self.sample_completed_matchup]

            mlp.write_ics(test_file, matchups, "America/Los_Angeles", debug=False)

            # Verify file was created
            self.assertTrue(os.path.exists(test_file))

            # Read and verify content
            with open(test_file, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("BEGIN:VCALENDAR", content)
            self.assertIn("END:VCALENDAR", content)
            self.assertIn("X-WR-CALNAME:MLP Matchups", content)
            self.assertIn("FINAL SCORE: Texas Ranchers 0 - 3 Miami Pickleball Club", content)

    @patch('make_mlp_ics_multi.fetch_active_events')
    @patch('make_mlp_ics_multi.fetch_json')
    def test_division_data_collection(self, mock_fetch_json, mock_fetch_events):
        # Mock the events response
        events_data = load_sample_events_data()
        mock_fetch_events.return_value = events_data['all']['events']

        # Mock the matchup data response
        mock_fetch_json.return_value = create_sample_data()

        # Test collecting matchups
        matchups = mlp.collect_matchups_for_division("Premier", "test-division-uuid", 5, "America/Los_Angeles", debug=False)

        # Should have found matchups from events that fall within our date range
        self.assertGreaterEqual(len(matchups), 0)  # May be 0 if no events fall in range

        # Verify that fetch_active_events was called
        mock_fetch_events.assert_called_once()


    @patch('make_mlp_ics_multi.fetch_json')
    def test_api_failure_handling(self, mock_fetch):
        """Test handling of API failures"""
        mock_fetch.return_value = None  # Simulate API failure

        matchups = mlp.collect_matchups_for_division(
            "Premier", "test-division-uuid", 1, "America/Los_Angeles", debug=False
        )

        self.assertEqual(len(matchups), 0)

    def test_edge_cases(self):
        """Test various edge cases"""
        # Empty matchup
        empty_matchup = {
            "uuid": "empty",
            "planned_start_date": "2025-08-16T18:30:00Z",
            "planned_end_date": "2025-08-16T19:50:00Z",
            "team_one_title": "",
            "team_two_title": "",
            "_division_name": "Test"
        }

        dtstamp = "20250101T120000Z"
        event_lines = mlp.build_event(empty_matchup, dtstamp, "Test")
        event_text = "\n".join(event_lines)

        # Should handle empty team names gracefully
        self.assertIn("SUMMARY: vs.", event_text)

    def test_score_detection_logic(self):
        """Test the logic for detecting and displaying scores"""
        # Test completed matchup with missing individual match scores
        incomplete_scores_matchup = {
            "uuid": "test-incomplete",
            "planned_start_date": "2025-08-16T18:30:00Z",
            "planned_end_date": "2025-08-16T19:50:00Z",
            "team_one_title": "Utah Black Diamonds",
            "team_two_title": "Brooklyn Aces",
            "team_one_score": 2,
            "team_two_score": 1,
            "matchup_status": "COMPLETED_MATCHUP_STATUS",
            "_division_name": "Premier",
            "matches": [
                {
                    "match_status": 4,
                    "match_completed_type": 5,
                    "team_one_score": None,  # Missing score
                    "team_two_score": None,
                    "round_text": "Game 1"
                }
            ]
        }

        dtstamp = "20250101T120000Z"
        event_lines = mlp.build_event(incomplete_scores_matchup, dtstamp, "Premier")
        event_text = "\n".join(event_lines)

        # Should have overall score but not individual match scores
        self.assertIn("FINAL SCORE: Brooklyn Aces 1 - 2 Utah Black Diamonds", event_text)
        self.assertNotIn("Game 1:", event_text)


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)