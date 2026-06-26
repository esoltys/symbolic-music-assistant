#!/usr/bin/env python3
import sys
import json
import argparse
from pathlib import Path

DURATION_MAP = {
    "whole": 4.0,
    "half": 2.0,
    "quarter": 1.0,
    "eighth": 0.5,
    "sixteenth": 0.25
}

def parse_time_signature(ts_str):
    try:
        num, den = map(int, ts_str.split("/"))
        return num * (4.0 / den)
    except Exception:
        return 4.0  # Default to 4 beats per measure if parsing fails

def main():
    parser = argparse.ArgumentParser(description="Hierarchical score construction manager.")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Sub-commands")

    # init sub-command
    init_parser = subparsers.add_parser("init", help="Initialize a blank score.")
    init_parser.add_argument("--time-signature", default="4/4", help="Time signature (default '4/4')")
    init_parser.add_argument("--key-signature", default="C Major", help="Key signature (default 'C Major')")
    init_parser.add_argument("--session-id", required=True, help="Unique ADK runtime session ID")

    # add sub-command
    add_parser = subparsers.add_parser("add", help="Add a note/chord/rest token to the score.")
    add_parser.add_argument("--pitch", required=True, help="Pitch name (e.g. 'C4', or comma-separated chord 'C4,E4,G4', or 'rest')")
    add_parser.add_argument("--duration", required=True, help="Duration (e.g. 'quarter', 'half', 'eighth')")
    add_parser.add_argument("--part-id", default="melody", help="ID of the part/track (default 'melody')")
    add_parser.add_argument("--session-id", required=True, help="Unique ADK runtime session ID")

    args = parser.parse_args()

    # Determine paths
    script_dir = Path(__file__).parent.resolve()
    assets_dir = script_dir.parent / "assets"
    state_file = assets_dir / f"canvas_{args.session_id}.json"

    try:
        if args.command == "init":
            assets_dir.mkdir(parents=True, exist_ok=True)
            
            state = {
                "time_signature": args.time_signature,
                "key_signature": args.key_signature,
                "parts": [
                    {
                        "id": "melody",
                        "name": "Melody",
                        "clef": "treble",
                        "measures": [
                            {
                                "number": 1,
                                "events": []
                            }
                        ]
                    }
                ]
            }
            
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
                
            print(json.dumps({
                "status": "success",
                "action": "init",
                "time_signature": args.time_signature,
                "key_signature": args.key_signature,
                "parts_count": len(state["parts"])
            }, indent=2))
            sys.exit(0)

        elif args.command == "add":
            if not state_file.is_file():
                raise FileNotFoundError(
                    "Score has not been initialized yet. Run 'init' first."
                )
                
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                
            # Parse pitches
            pitch_input = args.pitch.strip()
            if pitch_input.lower() == "rest" or not pitch_input:
                pitches = ["rest"]
            else:
                pitches = [p.strip() for p in pitch_input.split(",") if p.strip()]
            
            # Find or create part
            part_id = args.part_id.strip()
            part = None
            for p in state.get("parts", []):
                if p["id"] == part_id:
                    part = p
                    break
            
            if part is None:
                part = {
                    "id": part_id,
                    "name": part_id.capitalize(),
                    "clef": "bass" if "bass" in part_id.lower() else "treble",
                    "measures": [
                        {
                            "number": 1,
                            "events": []
                        }
                    ]
                }
                if "parts" not in state:
                    state["parts"] = []
                state["parts"].append(part)
                
            # Parse time signature and determine measure limits
            beats_per_measure = parse_time_signature(state.get("time_signature", "4/4"))
            
            # Get last measure
            measures = part["measures"]
            last_measure = measures[-1]
            
            # Calculate current beats in last measure
            current_beats = sum(DURATION_MAP.get(e["duration"].lower(), 1.0) for e in last_measure["events"])
            added_dur = DURATION_MAP.get(args.duration.lower(), 1.0)
            
            # Check for overflow
            if current_beats + added_dur - 1e-5 > beats_per_measure:
                # Create a new measure
                new_measure = {
                    "number": len(measures) + 1,
                    "events": []
                }
                measures.append(new_measure)
                last_measure = new_measure
            
            new_event = {
                "pitches": pitches,
                "duration": args.duration
            }
            last_measure["events"].append(new_event)
            
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
                
            print(json.dumps({
                "status": "success",
                "action": "add",
                "part_id": part_id,
                "added_event": new_event,
                "measure_number": last_measure["number"]
            }, indent=2))
            sys.exit(0)

    except Exception as e:
        print(json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()
