#!/usr/bin/env python3
import sys
import json
import argparse
import re
from music21 import pitch, interval

QUALITY_MAP = {
    "P": "Perfect",
    "M": "Major",
    "m": "Minor",
    "d": "Diminished",
    "dd": "Doubly Diminished",
    "A": "Augmented",
    "AA": "Doubly Augmented"
}

def get_ordinal(num_str: str) -> str:
    val = int(num_str)
    if 11 <= val % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(val % 10, "th")
    return f"{num_str}{suffix}"

def map_interval_name(m21_name: str) -> str:
    # Match letters prefix and digits suffix (e.g., P5, m3, AA4)
    match = re.match(r'^([a-zA-Z]+)(\d+)$', m21_name)
    if not match:
        return m21_name
    
    quality_code = match.group(1)
    number_str = match.group(2)
    
    quality = QUALITY_MAP.get(quality_code, quality_code)
    ordinal = get_ordinal(number_str)
    
    return f"{quality} {ordinal}"

def main():
    parser = argparse.ArgumentParser(description="Evaluate interval between two note pitches.")
    parser.add_argument("start_note", help="Starting note (e.g., C4)")
    parser.add_argument("end_note", help="Ending note (e.g., G4)")
    
    # Check if there are no arguments
    if len(sys.argv) < 3:
        print(json.dumps({
            "status": "error",
            "error": "Missing required arguments: start_note and end_note"
        }, indent=2))
        sys.exit(1)
        
    args = parser.parse_args()
    
    try:
        # Parse start note
        try:
            p_start = pitch.Pitch(args.start_note)
        except Exception as e:
            raise ValueError(f"Invalid start note format: {args.start_note}. Details: {e}")
            
        # Parse end note
        try:
            p_end = pitch.Pitch(args.end_note)
        except Exception as e:
            raise ValueError(f"Invalid end note format: {args.end_note}. Details: {e}")
            
        # Validate octave presence
        if p_start.octave is None:
            raise ValueError(f"Start note must include an octave: {args.start_note}")
        if p_end.octave is None:
            raise ValueError(f"End note must include an octave: {args.end_note}")
            
        # Validate MIDI/pitch range (MIDI range C0 to B8, i.e. 12 to 119)
        if not (12.0 <= p_start.ps <= 119.0):
            raise ValueError(f"Note out of valid MIDI/pitch range: {args.start_note}")
        if not (12.0 <= p_end.ps <= 119.0):
            raise ValueError(f"Note out of valid MIDI/pitch range: {args.end_note}")
            
        # Compute interval
        m21_interval = interval.Interval(p_start, p_end)
        
        # Get canonical interval name mapped to PRD format
        canonical_name = map_interval_name(m21_interval.name)
        
        result = {
            "status": "success",
            "start_note": args.start_note,
            "end_note": args.end_note,
            "semitones": m21_interval.semitones,
            "interval_name": canonical_name
        }
        print(json.dumps(result, indent=2))
        sys.exit(0)
        
    except Exception as e:
        print(json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()
