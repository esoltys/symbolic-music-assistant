#!/usr/bin/env python3
import sys
import json
import argparse
from music21 import scale, pitch

def main():
    parser = argparse.ArgumentParser(description="Generate scale pitches.")
    parser.add_argument("tonic", help="Tonic pitch name (e.g. C, F#, B-)")
    parser.add_argument("scale_type", help="Scale/mode type (e.g. major, minor, dorian, phrygian, lydian, mixolydian, aeolian, locrian)")
    
    if len(sys.argv) < 3:
        print(json.dumps({
            "status": "error",
            "error": "Missing required arguments: tonic and scale_type"
        }, indent=2))
        sys.exit(1)
        
    args = parser.parse_args()
    
    try:
        # Validate tonic input using music21.pitch.Pitch
        try:
            p = pitch.Pitch(args.tonic)
            tonic = p.name
        except Exception as e:
            raise ValueError(f"Invalid tonic note format: {args.tonic}. Details: {e}")
            
        scale_type = args.scale_type.strip().lower()
        
        # Instantiate music21 scale
        if scale_type in ["major", "ionian"]:
            s = scale.MajorScale(tonic)
        elif scale_type in ["minor", "natural minor", "aeolian"]:
            s = scale.MinorScale(tonic)
        elif scale_type == "dorian":
            s = scale.DorianScale(tonic)
        elif scale_type == "phrygian":
            s = scale.PhrygianScale(tonic)
        elif scale_type == "lydian":
            s = scale.LydianScale(tonic)
        elif scale_type == "mixolydian":
            s = scale.MixolydianScale(tonic)
        elif scale_type == "locrian":
            s = scale.LocrianScale(tonic)
        else:
            raise ValueError(f"Unsupported scale type: {scale_type}. Supported types: major, minor, dorian, phrygian, lydian, mixolydian, aeolian, locrian")
            
        # Get pitches from tonic in octave 4 up to tonic in octave 5
        start_pitch = f"{tonic}4"
        end_pitch = f"{tonic}5"
        pitches = [str(pt.nameWithOctave) for pt in s.getPitches(start_pitch, end_pitch)]
        
        result = {
            "status": "success",
            "tonic": tonic,
            "scale_type": scale_type,
            "pitches": pitches
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
