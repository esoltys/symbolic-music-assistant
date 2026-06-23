#!/usr/bin/env python3
import sys
import json
import argparse
from pathlib import Path
import pretty_midi

def main():
    parser = argparse.ArgumentParser(description="Extract metrics from a MIDI file.")
    parser.add_argument("--file-path", required=True, help="Path to the MIDI file")
    
    # Check if there are no arguments
    if len(sys.argv) < 2:
        print(json.dumps({
            "status": "error",
            "error": "Missing required argument: --file-path"
        }, indent=2))
        sys.exit(1)
        
    args = parser.parse_args()
    
    file_path = Path(args.file_path)
    
    try:
        # Check if file exists
        if not file_path.is_file():
            raise FileNotFoundError(f"MIDI file not found: {args.file_path}")
            
        # Parse MIDI using pretty_midi
        try:
            pm = pretty_midi.PrettyMIDI(str(file_path))
        except Exception as e:
            raise ValueError(f"Failed to parse MIDI file. It may be corrupt or invalid. Details: {e}")
            
        # Extract metrics
        track_count = len(pm.instruments)
        note_count = sum(len(inst.notes) for inst in pm.instruments)
        
        # Get tempo (first tempo event or default)
        tempo_times, tempo_bpms = pm.get_tempo_changes()
        global_tempo = float(tempo_bpms[0]) if len(tempo_bpms) > 0 else 120.0
        
        result = {
            "status": "success",
            "file_path": args.file_path,
            "track_count": track_count,
            "tempo": global_tempo,
            "note_count": note_count
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
