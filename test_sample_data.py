
#!/usr/bin/env python3
"""
Generate sample test data for MLP ICS testing
"""

import json


def create_sample_data():
    """Create sample API response data for testing"""
    
    completed_matchup = {
        "uuid": "sample-completed-123",
        "planned_start_date": "2025-08-16T18:30:00Z",
        "planned_end_date": "2025-08-16T19:50:00Z",
        "team_one_title": "Miami Pickleball Club",
        "team_two_title": "Texas Ranchers",
        "team_one_score": 3,
        "team_two_score": 0,
        "matchup_status": "COMPLETED_MATCHUP_STATUS",
        "matchup_completed_type": "PLAYED_MATCHUP_COMPLETION_TYPE",
        "team_league_title": "Major League Pickleball",
        "matchup_group_title": "Premier Season",
        "venue": "Dreamland Courts",
        "courts": [{"title": "GS"}],
        "matches": [
            {
                "match_uuid": "match-1",
                "match_status": 4,
                "match_completed_type": 5,
                "team_one_score": 11,
                "team_two_score": 9,
                "court_title": "GS",
                "round_text": "Mixed Doubles",
                "team_one_player_one_name": "Anna Leigh Waters",
                "team_one_player_two_name": "Ben Johns",
                "team_two_player_one_name": "Catherine Parenteau",
                "team_two_player_two_name": "Matt Wright"
            },
            {
                "match_uuid": "match-2",
                "match_status": 4,
                "match_completed_type": 5,
                "team_one_score": 11,
                "team_two_score": 7,
                "court_title": "GS",
                "round_text": "Women's Doubles",
                "team_one_player_one_name": "Anna Leigh Waters",
                "team_one_player_two_name": "Meghan Dizon",
                "team_two_player_one_name": "Catherine Parenteau",
                "team_two_player_two_name": "Jade Kawamoto"
            },
            {
                "match_uuid": "match-3",
                "match_status": 4,
                "match_completed_type": 5,
                "team_one_score": 11,
                "team_two_score": 5,
                "court_title": "GS",
                "round_text": "Men's Doubles",
                "team_one_player_one_name": "Ben Johns",
                "team_one_player_two_name": "Dylan Frazier",
                "team_two_player_one_name": "Matt Wright",
                "team_two_player_two_name": "Riley Newman"
            }
        ]
    }
    
    in_progress_matchup = {
        "uuid": "sample-in-progress-456",
        "planned_start_date": "2025-08-16T22:00:00Z",
        "planned_end_date": "2025-08-16T23:20:00Z",
        "team_one_title": "Utah Black Diamonds", 
        "team_two_title": "Brooklyn Aces",
        "team_one_score": 1,
        "team_two_score": 1,
        "matchup_status": "IN_PROGRESS_MATCHUP_STATUS",
        "team_league_title": "Major League Pickleball",
        "matchup_group_title": "Challenger Season",
        "venue": "Brooklyn Courts",
        "courts": [{"title": "CC"}],
        "matches": [
            {
                "match_uuid": "match-4",
                "match_status": 4,
                "match_completed_type": 5,
                "team_one_score": 11,
                "team_two_score": 8,
                "court_title": "CC",
                "round_text": "Mixed Doubles"
            },
            {
                "match_uuid": "match-5",
                "match_status": 4,
                "match_completed_type": 5,
                "team_one_score": 9,
                "team_two_score": 11,
                "court_title": "CC",
                "round_text": "Women's Doubles"
            },
            {
                "match_uuid": "match-6",
                "match_status": 2,  # In progress
                "match_completed_type": 0,
                "team_one_score": 5,
                "team_two_score": 7,
                "court_title": "CC",
                "round_text": "Men's Doubles"
            }
        ]
    }
    
    upcoming_matchup = {
        "uuid": "sample-upcoming-789",
        "planned_start_date": "2025-08-17T20:00:00Z",
        "planned_end_date": "2025-08-17T21:20:00Z",
        "team_one_title": "Atlanta Bouncers",
        "team_two_title": "Chicago Slice",
        "team_one_score": 0,
        "team_two_score": 0,
        "matchup_status": "READY_TO_BE_STARTED_STATUS",
        "team_league_title": "Major League Pickleball",
        "matchup_group_title": "Premier Season",
        "venue": "Atlanta Pickleball Center",
        "courts": [{"title": "GS"}],
        "matches": []
    }
    
    api_response = {
        "results": {
            "system_matchups": [
                completed_matchup,
                in_progress_matchup,
                upcoming_matchup
            ]
        }
    }
    
    return api_response


if __name__ == "__main__":
    sample_data = create_sample_data()
    
    # Write to file for reference
    with open("sample_test_data.json", "w") as f:
        json.dump(sample_data, f, indent=2)
    
    print("Sample test data created in sample_test_data.json")
    print(f"Generated {len(sample_data['results']['system_matchups'])} sample matchups")
