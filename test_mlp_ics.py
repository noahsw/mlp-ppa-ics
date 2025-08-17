
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
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Import the module we're testing
import make_mlp_ics_multi as mlp


class TestMLPICSGenerator(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        self.sample_completed_matchup = {
            "uuid": "test-uuid-123",
            "planned_start_date": "2025-08-16T18:30:00Z",
            "planned_end_date": "2025-08-16T19:50:00Z",
            "team_one_title": "Home Team",
            "team_two_title": "Away Team",
            "team_one_score": 3,
            "team_two_score": 0,
            "matchup_status": "COMPLETED_MATCHUP_STATUS",
            "team_league_title": "Major League Pickleball",
            "matchup_group_title": "Premier Season",
            "venue": "Test Venue",
            "_division_name": "Premier",
            "matches": [
                {
                    "match_status": 4,
                    "match_completed_type": 5,
                    "team_one_score": 11,
                    "team_two_score": 9,
                    "court_title": "GS",
                    "round_text": "Game 1",
                    "team_one_player_one_name": "John Doe",
                    "team_one_player_two_name": "Jane Smith",
                    "team_two_player_one_name": "Bob Wilson",
                    "team_two_player_two_name": "Alice Brown"
                },
                {
                    "match_status": 4,
                    "match_completed_type": 5,
                    "team_one_score": 11,
                    "team_two_score": 7,
                    "court_title": "GS",
                    "round_text": "Game 2",
                    "team_one_player_one_name": "John Doe",
                    "team_one_player_two_name": "Jane Smith",
                    "team_two_player_one_name": "Bob Wilson",
                    "team_two_player_two_name": "Alice Brown"
                }
            ]
        }

        self.sample_in_progress_matchup = {
            "uuid": "test-uuid-456",
            "planned_start_date": "2025-08-17T20:00:00Z",
            "planned_end_date": "2025-08-17T21:20:00Z",
            "team_one_title": "Team Alpha",
            "team_two_title": "Team Beta",
            "team_one_score": 1,
            "team_two_score": 0,
            "matchup_status": "IN_PROGRESS_MATCHUP_STATUS",
            "team_league_title": "Major League Pickleball",
            "matchup_group_title": "Challenger Season",
            "venue": "Test Arena",
            "_division_name": "Challenger",
            "matches": [
                {
                    "match_status": 4,
                    "match_completed_type": 5,
                    "team_one_score": 11,
                    "team_two_score": 8,
                    "court_title": "CC",
                    "round_text": "Game 1"
                }
            ]
        }

        self.sample_upcoming_matchup = {
            "uuid": "test-uuid-789",
            "planned_start_date": "2025-08-18T19:00:00Z",
            "planned_end_date": "2025-08-18T20:20:00Z",
            "team_one_title": "Future Home",
            "team_two_title": "Future Away",
            "matchup_status": "READY_TO_BE_STARTED_STATUS",
            "team_league_title": "Major League Pickleball",
            "matchup_group_title": "Premier Season",
            "venue": "Future Venue",
            "_division_name": "Premier",
            "matches": []
        }

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
        
        self.assertEqual(sorted(away_players), ["Alice Brown", "Bob Wilson"])
        self.assertEqual(sorted(home_players), ["Jane Smith", "John Doe"])

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
        self.assertIn("UID:test-uuid-123@mlp", event_text)
        self.assertIn("SUMMARY:Away Team vs. Home Team", event_text)
        
        # Check for score information in description
        self.assertIn("FINAL SCORE: Away Team 0 - 3 Home Team", event_text)
        self.assertIn("Game 1: Away Team 9 - 11 Home Team", event_text)
        self.assertIn("Game 2: Away Team 7 - 11 Home Team", event_text)
        
        # Check for player information
        self.assertIn("Alice Brown; Bob Wilson", event_text)
        self.assertIn("Jane Smith; John Doe", event_text)

    def test_in_progress_matchup_event_generation(self):
        """Test event generation for in-progress matchup"""
        dtstamp = "20250101T120000Z"
        event_lines = mlp.build_event(self.sample_in_progress_matchup, dtstamp, "Challenger")
        
        event_text = "\n".join(event_lines)
        
        # Should not have FINAL SCORE for in-progress
        self.assertNotIn("FINAL SCORE", event_text)
        # But should have division info
        self.assertIn("Division: Challenger", event_text)

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
        
        gs_filtered = mlp.filter_by_primary_court(matchups, "GS")
        self.assertEqual(len(gs_filtered), 2)
        self.assertEqual([m["uuid"] for m in gs_filtered], ["1", "3"])
        
        cc_filtered = mlp.filter_by_primary_court(matchups, "CC")
        self.assertEqual(len(cc_filtered), 1)
        self.assertEqual(cc_filtered[0]["uuid"], "2")

    def test_ics_file_writing(self):
        """Test writing ICS file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test.ics")
            matchups = [self.sample_completed_matchup]
            
            mlp.write_ics(test_file, matchups, "America/Los_Angeles")
            
            # Verify file was created
            self.assertTrue(os.path.exists(test_file))
            
            # Read and verify content
            with open(test_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            self.assertIn("BEGIN:VCALENDAR", content)
            self.assertIn("END:VCALENDAR", content)
            self.assertIn("X-WR-CALNAME:MLP Matchups", content)
            self.assertIn("FINAL SCORE: Away Team 0 - 3 Home Team", content)

    @patch('make_mlp_ics_multi.fetch_json')
    def test_division_data_collection(self, mock_fetch):
        """Test collecting matchups for a division"""
        # Mock API response
        mock_response = {
            "results": {
                "system_matchups": [self.sample_completed_matchup]
            }
        }
        mock_fetch.return_value = mock_response
        
        matchups = mlp.collect_matchups_for_division(
            "Premier", "test-division-uuid", 1, "America/Los_Angeles"
        )
        
        self.assertEqual(len(matchups), 1)
        self.assertEqual(matchups[0]["uuid"], "test-uuid-123")
        self.assertEqual(matchups[0]["_division_name"], "Premier")

    @patch('make_mlp_ics_multi.fetch_json')
    def test_api_failure_handling(self, mock_fetch):
        """Test handling of API failures"""
        mock_fetch.return_value = None  # Simulate API failure
        
        matchups = mlp.collect_matchups_for_division(
            "Premier", "test-division-uuid", 1, "America/Los_Angeles"
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
            "team_one_title": "Home",
            "team_two_title": "Away",
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
        self.assertIn("FINAL SCORE: Away 1 - 2 Home", event_text)
        self.assertNotIn("Game 1:", event_text)


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
