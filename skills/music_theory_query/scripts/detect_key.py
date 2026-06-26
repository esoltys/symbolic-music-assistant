#!/usr/bin/env python3
import sys
import json
import argparse
from pathlib import Path
from music21 import stream, note, chord, meter, key as m21_key, pitch, converter

DURATION_MAP = {
    "whole": 4.0,
    "half": 2.0,
    "quarter": 1.0,
    "eighth": 0.5,
    "sixteenth": 0.25
}

def load_score_from_json(json_path: Path) -> stream.Score:
    with open(json_path, "r", encoding="utf-8") as f:
        state = json.load(f)
        
    m21_score = stream.Score()
    ts_str = state.get("time_signature", "4/4")
    
    for part_idx, part in enumerate(state.get("parts", [])):
        m21_part = stream.Part()
        m21_part.id = part.get("id", f"part_{part_idx}")
        
        for measure_idx, measure_item in enumerate(part.get("measures", [])):
            m21_measure = stream.Measure()
            m21_measure.number = measure_item.get("number", measure_idx + 1)
            
            for event in measure_item.get("events", []):
                pitches = event.get("pitches", ["rest"])
                duration_str = event.get("duration", "quarter").lower()
                dur_val = DURATION_MAP.get(duration_str, 1.0)
                
                if not pitches or "rest" in [p.lower() for p in pitches]:
                    r = note.Rest()
                    r.quarterLength = dur_val
                    m21_measure.append(r)
                elif len(pitches) == 1:
                    n = note.Note(pitches[0])
                    n.quarterLength = dur_val
                    m21_measure.append(n)
                else:
                    c = chord.Chord(pitches)
                    c.quarterLength = dur_val
                    m21_measure.append(c)
                    
            m21_part.append(m21_measure)
        m21_score.append(m21_part)
        
    return m21_score

def main():
    parser = argparse.ArgumentParser(description="Detect key signature using music21 key analysis.")
    parser.add_argument("--midi-path", help="Path to the MIDI file to analyze")
    parser.add_argument("--score-path", help="Path to the score state JSON file to analyze")
    parser.add_argument("--session-id", help="Session ID to locate score state JSON file")
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent.parent.parent.resolve()
    
    try:
        s = None
        source_name = ""
        
        if args.midi_path:
            midi_file_path = Path(args.midi_path)
            if not midi_file_path.is_file():
                raise FileNotFoundError(f"MIDI file not found: {args.midi_path}")
            s = converter.parse(str(midi_file_path))
            source_name = midi_file_path.name
            
        elif args.score_path or args.session_id:
            if args.score_path:
                score_file_path = Path(args.score_path)
            else:
                score_file_path = project_root / "skills" / "score_construction" / "assets" / f"score_{args.session_id}.json"
                
            if not score_file_path.is_file():
                raise FileNotFoundError(f"Score file not found: {score_file_path}")
            s = load_score_from_json(score_file_path)
            source_name = score_file_path.name
            
        else:
            raise ValueError("Must provide either --midi-path, --score-path, or --session-id")
            
        # Analyze key using music21
        k = s.analyze('key')
        
        detected_key = f"{k.tonic.name} {k.mode.capitalize()}"
        confidence = getattr(k, "tonalAnalysisCoefficient", 0.0)
        
        # Get alternative keys if possible
        alternatives = []
        try:
            alt_keys = k.getAlternativeKeys(3)
            for alt in alt_keys:
                alt_name = f"{alt.tonic.name} {alt.mode.capitalize()}"
                if alt_name != detected_key:
                    alternatives.append({
                        "key": alt_name,
                        "confidence": round(getattr(alt, "tonalAnalysisCoefficient", 0.0), 4)
                    })
        except Exception:
            pass
            
        result = {
            "status": "success",
            "source": source_name,
            "detected_key": detected_key,
            "confidence": round(confidence, 4),
            "alternatives": alternatives
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
