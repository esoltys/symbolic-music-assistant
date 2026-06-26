#!/usr/bin/env python3
import sys
import json
import re
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Import music21 elements
from music21 import stream, note, chord, clef, meter, key

DURATION_MAP = {
    "whole": 4.0,
    "half": 2.0,
    "quarter": 1.0,
    "eighth": 0.5,
    "sixteenth": 0.25
}

PART_COLORS = ['#2b5c8f', '#a83232', '#32a852', '#a88332', '#7b32a8']

def pitch_to_midi(pitch_str):
    if pitch_str.lower() == "rest":
        return None
    # Parse note name, optional accidental, and octave (e.g. C4, F#3, E-5)
    pattern = r"^([A-G])([#\-]?)(-?\d+)$"
    match = re.match(pattern, pitch_str, re.IGNORECASE)
    if not match:
        raise ValueError(f"Invalid pitch format: {pitch_str}")
    
    note_name = match.group(1).upper()
    alteration = match.group(2)
    octave = int(match.group(3))
    
    semitones = {
        'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11
    }
    
    pitch_val = 12 * (octave + 1) + semitones[note_name]
    if alteration == '#':
        pitch_val += 1
    elif alteration == '-':
        pitch_val -= 1
        
    return pitch_val

def main():
    parser = argparse.ArgumentParser(description="Render hierarchical score state to visual plots and MusicXML.")
    parser.add_argument("--canvas-path", help="Path to the canvas state JSON file")
    parser.add_argument("--session-id", required=True, help="Unique ADK runtime session ID")
    args = parser.parse_args()

    # Determine paths
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent.parent.parent.resolve()
    
    if args.canvas_path:
        canvas_path = Path(args.canvas_path)
    else:
        canvas_path = project_root / "skills" / "score_construction" / "assets" / f"canvas_{args.session_id}.json"
        
    assets_dir = script_dir.parent / "assets"
    
    try:
        if not canvas_path.is_file():
            raise FileNotFoundError(f"Canvas state file not found: {canvas_path}")
            
        with open(canvas_path, "r", encoding="utf-8") as f:
            state = json.load(f)
            
        parts = state.get("parts", [])
        if not parts:
            raise ValueError("Canvas has no parts to render.")
            
        # Ensure output assets folder exists
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        # Parse notes to compute time steps and MIDI pitches for matplotlib
        note_data = []
        max_time = 0.0
        
        for part_idx, part in enumerate(parts):
            current_time = 0.0
            part_id = part.get("id", f"part_{part_idx}")
            
            for measure in part.get("measures", []):
                for event in measure.get("events", []):
                    pitch_list = event.get("pitches", ["rest"])
                    duration_str = event.get("duration", "quarter").lower()
                    dur = DURATION_MAP.get(duration_str, 1.0)
                    
                    if not pitch_list or "rest" in [p.lower() for p in pitch_list]:
                        current_time += dur
                        continue
                        
                    for pitch_str in pitch_list:
                        try:
                            midi = pitch_to_midi(pitch_str)
                            if midi is not None:
                                note_data.append((current_time, current_time + dur, midi, pitch_str, part_idx, part_id))
                        except ValueError:
                            pass
                    current_time += dur
            if current_time > max_time:
                max_time = current_time
                
        if not note_data:
            raise ValueError("Canvas contains only rests, no notes to visualize.")
            
        # Unique pitches for Y-axis ticks
        unique_pitches = {}
        for _, _, midi, pitch, _, _ in note_data:
            unique_pitches[midi] = pitch
            
        sorted_midi = sorted(unique_pitches.keys())
        sorted_labels = [unique_pitches[m] for m in sorted_midi]
        
        # 1. Piano Roll Export (Matplotlib)
        plt.figure(figsize=(10, 5))
        plt.title("Score Piano Roll View (Multi-Part)", fontsize=14, fontweight='bold', pad=15)
        plt.xlabel("Time (Beats)", fontsize=11, labelpad=10)
        plt.ylabel("Pitch", fontsize=11, labelpad=10)
        plt.grid(True, which='both', linestyle='--', alpha=0.5)
        
        # Plot horizontal segments for each part
        plotted_parts = set()
        for start, end, midi, pitch, part_idx, part_id in note_data:
            color = PART_COLORS[part_idx % len(PART_COLORS)]
            label = part_id if part_id not in plotted_parts else ""
            if label:
                plotted_parts.add(part_id)
            plt.plot([start, end], [midi, midi], color=color, linewidth=8, solid_capstyle='butt', label=label)
            
        plt.yticks(sorted_midi, sorted_labels)
        if len(sorted_midi) == 1:
            plt.ylim(sorted_midi[0] - 1, sorted_midi[0] + 1)
        else:
            plt.ylim(sorted_midi[0] - 0.5, sorted_midi[-1] + 0.5)
            
        plt.xlim(-0.2, max_time + 0.2)
        if plotted_parts:
            plt.legend(loc='upper right')
            
        plt.tight_layout()
        
        piano_roll_path = assets_dir / f"piano_roll_{args.session_id}.png"
        score_plot_path = assets_dir / f"score_plot_{args.session_id}.png"
        plt.savefig(piano_roll_path, dpi=150)
        plt.savefig(score_plot_path, dpi=150)
        plt.close()
        
        # 2. music21 MusicXML Export
        m21_score = stream.Score()
        ts_str = state.get("time_signature", "4/4")
        ks_str = state.get("key_signature", "C Major")
        
        for part_idx, part in enumerate(parts):
            m21_part = stream.Part()
            m21_part.id = part.get("id", f"part_{part_idx}")
            
            for measure_idx, measure_item in enumerate(part.get("measures", [])):
                m21_measure = stream.Measure()
                m21_measure.number = measure_item.get("number", measure_idx + 1)
                
                # Add metadata to the first measure
                if measure_idx == 0:
                    clef_str = part.get("clef", "treble").lower()
                    if clef_str == "bass":
                        m21_measure.append(clef.BassClef())
                    else:
                        m21_measure.append(clef.TrebleClef())
                    m21_measure.append(meter.TimeSignature(ts_str))
                    ks_parts = ks_str.strip().split()
                    tonic = ks_parts[0]
                    mode = ks_parts[1].lower() if len(ks_parts) > 1 else "major"
                    m21_measure.append(key.Key(tonic, mode))
                    
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
            
        # Export score to MusicXML
        musicxml_path = assets_dir / f"score_{args.session_id}.musicxml"
        m21_score.write("musicxml", fp=str(musicxml_path))
        
        # Make relative paths from project root for portability
        rel_piano_roll = piano_roll_path.relative_to(project_root).as_posix()
        rel_score_xml = musicxml_path.relative_to(project_root).as_posix()
        
        print(json.dumps({
            "status": "success",
            "piano_roll": rel_piano_roll,
            "score_xml": rel_score_xml
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
