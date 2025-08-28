
#!/usr/bin/env python3
"""
Test script for PPA ICS parser
"""

import sys
import subprocess

def main():
    print("Testing PPA ICS Generator...")
    print("=" * 50)
    
    # Test with local example file
    try:
        result = subprocess.run([
            sys.executable, "make_ppa_ics.py",
            "--file", "sample_ppa_schedule.html",
            "--tournament", "Open at the Las Vegas Strip",
            "--output", "test_ppa_schedule.ics",
            "--debug"
        ], capture_output=True, text=True, check=True)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        print("\nTest completed successfully!")
        print("Check test_ppa_schedule.ics for the generated calendar.")
        
    except subprocess.CalledProcessError as e:
        print(f"Test failed with exit code {e.returncode}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
