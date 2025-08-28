
#!/usr/bin/env python3
"""
Test runner specifically for PPA ICS generator tests
"""

import unittest
import sys
import os

def run_ppa_tests():
    """Run only PPA test cases"""
    
    print("Running PPA ICS Generator Test Suite...")
    print("=" * 60)
    
    # Load only the PPA tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName('test_ppa_parser.TestPPAICSGenerator')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print(f"\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print(f"\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    if result.wasSuccessful():
        print(f"\n✅ All PPA tests passed!")
        return 0
    else:
        print(f"\n❌ Some PPA tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(run_ppa_tests())
