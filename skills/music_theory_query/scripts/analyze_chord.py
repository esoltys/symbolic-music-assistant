#!/usr/bin/env python3
import sys
import json
import argparse
from music21 import chord, key, roman

def main():
    parser = argparse.ArgumentParser(description="Analyze a chord.")
    parser.add_argument("pitches", help="Comma-separated pitch names (e.g., C4,E4,G4)")
    parser.add_argument("--key", help="Key signature for Roman numeral analysis (e.g., C Major)")
    
    if len(sys.argv) < 2:
        print(json.dumps({
            "status": "error",
            "error": "Missing required argument: pitches"
        }, indent=2))
        sys.exit(1)
        
    args = parser.parse_args()
    
    try:
        pitch_list = [p.strip() for p in args.pitches.split(",") if p.strip()]
        if not pitch_list:
            raise ValueError("No pitches provided.")
            
        c = chord.Chord(pitch_list)
        
        result = {
            "status": "success",
            "pitches": pitch_list,
            "common_name": c.commonName,
            "full_name": c.fullName,
            "inversion": c.inversion(),
            "is_triad": c.isTriad()
        }
        
        if args.key:
            # Parse key signature robustly
            ks_parts = args.key.strip().split()
            tonic = ks_parts[0]
            mode = ks_parts[1].lower() if len(ks_parts) > 1 else "major"
            
            # Map flat/sharp descriptions if user typed them
            # e.g., E-flat -> E-
            tonic = tonic.replace("flat", "-").replace("Flat", "-").replace("sharp", "#").replace("Sharp", "#")
            
            k = key.Key(tonic, mode)
            rn = roman.romanNumeralFromChord(c, k)
            result["roman_numeral"] = rn.figure
            result["key"] = f"{tonic} {mode.capitalize()}"
            
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
