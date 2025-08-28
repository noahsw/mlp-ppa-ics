
#!/usr/bin/env python3
"""
Test suite for ics_utils.py

Tests shared ICS utility functions including:
- ICS special character escaping
- ICS line folding
- ICS file structure helpers
"""

import unittest
from typing import List
import ics_utils


class TestICSUtils(unittest.TestCase):
    """Test cases for ICS utility functions"""

    def test_ics_escaping(self):
        """Test ICS special character escaping"""
        test_cases = [
            ("Hello, World!", "Hello\\, World!"),
            ("Line1\nLine2", "Line1\\nLine2"),
            ("Semi;colon", "Semi\\;colon"),
            ("Back\\slash", "Back\\\\slash"),
            ("All,bad;chars\nhere\\", "All\\,bad\\;chars\\nhere\\\\"),
            ("Mixed's/Women's Doubles", "Mixed's/Women's Doubles"),  # Apostrophes should be preserved
            ("", ""),  # Empty string
            ("No special chars", "No special chars"),  # No escaping needed
        ]

        for input_str, expected in test_cases:
            result = ics_utils.ics_escape(input_str)
            self.assertEqual(result, expected, f"Failed to escape '{input_str}'")

    def test_ics_line_folding(self):
        """Test ICS line folding for long lines"""
        # Test short line (no folding needed)
        short_line = "SUMMARY:Short title"
        folded = ics_utils.fold_ical_line(short_line)
        self.assertEqual(folded, [short_line])

        # Test long line (folding needed)
        long_line = "DESCRIPTION:" + "A" * 100
        folded = ics_utils.fold_ical_line(long_line, limit=75)
        self.assertGreater(len(folded), 1, "Long line should be folded")
        self.assertTrue(folded[1].startswith(" "), "Continuation line should start with space")

        # Test custom limit
        custom_line = "X" * 50
        folded = ics_utils.fold_ical_line(custom_line, limit=25)
        self.assertGreater(len(folded), 1, "Should fold at custom limit")
        self.assertEqual(len(folded[0]), 25, "First part should be exactly 25 chars")

        # Test empty line
        empty_folded = ics_utils.fold_ical_line("")
        self.assertEqual(empty_folded, [""])

        # Test line exactly at limit
        exact_line = "X" * 75
        exact_folded = ics_utils.fold_ical_line(exact_line, limit=75)
        self.assertEqual(exact_folded, [exact_line], "Line exactly at limit should not be folded")

    def test_ics_header_generation(self):
        """Test ICS calendar header generation"""
        # Test with default timezone
        header = ics_utils.get_ics_header("Test Calendar")
        expected_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//MLP-PPA ICS Generator//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:Test Calendar",
            "X-WR-TIMEZONE:America/New_York",
        ]
        self.assertEqual(header, expected_lines)

        # Test with custom timezone
        header_custom = ics_utils.get_ics_header("Custom Calendar", "America/Los_Angeles")
        self.assertIn("X-WR-CALNAME:Custom Calendar", header_custom)
        self.assertIn("X-WR-TIMEZONE:America/Los_Angeles", header_custom)

        # Test with special characters in calendar name
        header_special = ics_utils.get_ics_header("Calendar, with; special\nchars\\")
        self.assertIn("X-WR-CALNAME:Calendar\\, with\\; special\\nchars\\\\", header_special)

    def test_ics_footer_generation(self):
        """Test ICS calendar footer generation"""
        footer = ics_utils.get_ics_footer()
        self.assertEqual(footer, ["END:VCALENDAR"])

    def test_fold_event_lines(self):
        """Test folding multiple event lines"""
        event_lines = [
            "SUMMARY:Short title",
            "DESCRIPTION:" + "Very long description that should be folded " * 5,
            "LOCATION:Simple location"
        ]

        folded = ics_utils.fold_event_lines(event_lines)
        
        # Should have more lines due to folding
        self.assertGreaterEqual(len(folded), len(event_lines))
        
        # First and third lines should remain unchanged
        self.assertEqual(folded[0], "SUMMARY:Short title")
        
        # Long description should be folded
        description_lines = [line for line in folded if line.startswith("DESCRIPTION:") or line.startswith(" ")]
        self.assertGreater(len(description_lines), 1, "Long description should be folded")
        
        # Continuation lines should start with space
        for line in description_lines[1:]:
            self.assertTrue(line.startswith(" "), "Continuation lines should start with space")

    def test_edge_cases(self):
        """Test various edge cases"""
        # Test None inputs (should not crash, though typically not called with None)
        # These would typically cause AttributeError in real usage, which is expected
        
        # Test very long lines
        very_long_line = "X" * 1000
        folded = ics_utils.fold_ical_line(very_long_line, limit=75)
        
        # Verify all parts except first start with space
        for i, part in enumerate(folded):
            if i > 0:
                self.assertTrue(part.startswith(" "), f"Part {i} should start with space")
        
        # Verify reconstructed line matches original (minus folding spaces)
        reconstructed = folded[0] + "".join(part[1:] for part in folded[1:])
        self.assertEqual(reconstructed, very_long_line)

    def test_integration_with_real_ics_content(self):
        """Test integration with realistic ICS content"""
        # Create a realistic event description with comma that needs escaping
        description = "Tournament: Open at the Las Vegas Strip\nCategory: Mixed Doubles, Championship\nCourt: Championship Court\nBroadcaster: PickleballTV"
        
        # Test escaping
        escaped = ics_utils.ics_escape(description)
        self.assertIn("\\n", escaped)
        self.assertIn("\\,", escaped)
        
        # Create a full event line
        full_line = f"DESCRIPTION:{escaped}"
        
        # Test folding
        folded = ics_utils.fold_ical_line(full_line)
        
        # Should handle the realistic content properly
        self.assertTrue(len(folded) >= 1)
        
        # Test header with tournament name
        header = ics_utils.get_ics_header("PPA Open at the Las Vegas Strip")
        self.assertIn("X-WR-CALNAME:PPA Open at the Las Vegas Strip", header)
        
        # Test complete calendar structure
        all_lines = []
        all_lines.extend(header)
        all_lines.extend(folded)
        all_lines.extend(ics_utils.get_ics_footer())
        
        # Should start and end properly
        self.assertTrue(all_lines[0].startswith("BEGIN:VCALENDAR"))
        self.assertTrue(all_lines[-1].startswith("END:VCALENDAR"))


def run_test_suite():
    """Run the ICS utils test suite with detailed output"""
    print("Running ICS Utils Test Suite...")
    print("=" * 50)

    suite = unittest.TestLoader().loadTestsFromTestCase(TestICSUtils)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print(f"\n{'='*50}")
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
        print(f"\n✅ All ICS utils tests passed!")
        return True
    else:
        print(f"\n❌ Some ICS utils tests failed!")
        return False


if __name__ == "__main__":
    import sys
    success = run_test_suite()
    sys.exit(0 if success else 1)
