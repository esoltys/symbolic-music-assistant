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

def parse_time_signature(ts_str):
    try:
        num, den = map(int, ts_str.split("/"))
        return num * (4.0 / den)
    except Exception:
        return 4.0

def get_time_signature_for_measure(measure_num, time_signatures_list):
    ts_list = sorted(time_signatures_list, key=lambda x: x["measure"])
    current_ts = "4/4"
    for ts in ts_list:
        if ts["measure"] <= measure_num:
            current_ts = ts["ratio"]
        else:
            break
    return current_ts

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
    parser.add_argument("--score-path", help="Path to the score state JSON file")
    parser.add_argument("--session-id", required=True, help="Unique ADK runtime session ID")
    args = parser.parse_args()

    # Determine paths
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent.parent.parent.resolve()
    
    if args.score_path:
        score_path = Path(args.score_path)
    else:
        score_path = project_root / "skills" / "score_construction" / "assets" / f"score_{args.session_id}.json"
        
    assets_dir = script_dir.parent / "assets"
    
    try:
        if not score_path.is_file():
            raise FileNotFoundError(f"Score state file not found: {score_path}")
            
        with open(score_path, "r", encoding="utf-8") as f:
            state = json.load(f)
            
        parts = state.get("parts", [])
        if not parts:
            raise ValueError("Score has no parts to render.")
            
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
            raise ValueError("Score contains only rests, no notes to visualize.")
            
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
        ks_str = state.get("key_signature", "C Major")
        time_signatures = state.get("time_signatures", [{"measure": 1, "ratio": state.get("time_signature", "4/4")}])
        
        # Precompute the max duration of each measure across all parts to handle missing/incomplete time signatures
        measure_max_beats = {}
        for part in parts:
            for measure_item in part.get("measures", []):
                m_num = measure_item.get("number")
                events = measure_item.get("events", [])
                beats = sum(DURATION_MAP.get(e.get("duration", "quarter").lower(), 1.0) for e in events)
                if m_num is not None:
                    measure_max_beats[m_num] = max(measure_max_beats.get(m_num, 0.0), beats)

        for part_idx, part in enumerate(parts):
            m21_part = stream.Part()
            m21_part.id = part.get("id", f"part_{part_idx}")
            
            # Resolve instrument based on program and percussion flag
            from music21 import instrument
            if part.get("is_percussion", False):
                inst = instrument.Percussion()
            else:
                program = part.get("program", 0)
                try:
                    inst = instrument.instrumentFromMidiProgram(program)
                except Exception:
                    inst = instrument.Instrument()
            inst.partName = part.get("name", f"Part {part_idx + 1}")
            inst.partId = part.get("id", f"part_{part_idx}")
            
            previous_ts = None
            for measure_idx, measure_item in enumerate(part.get("measures", [])):
                m21_measure = stream.Measure()
                m_num = measure_item.get("number", measure_idx + 1)
                m21_measure.number = m_num
                
                ts_str = get_time_signature_for_measure(m_num, time_signatures)
                expected_beats = parse_time_signature(ts_str)
                # Fallback: pad to the longest part's duration in this measure if it exceeds time signature
                expected_beats = max(expected_beats, measure_max_beats.get(m_num, 0.0))
                
                # Add time signature if it changes
                if ts_str != previous_ts:
                    m21_measure.append(meter.TimeSignature(ts_str))
                    previous_ts = ts_str
                
                # Add metadata to the first measure
                if measure_idx == 0:
                    m21_measure.append(inst)
                    clef_str = part.get("clef", "treble").lower()
                    if clef_str == "bass":
                        m21_measure.append(clef.BassClef())
                    else:
                        m21_measure.append(clef.TrebleClef())
                    ks_parts = ks_str.strip().split()
                    tonic = ks_parts[0]
                    mode = ks_parts[1].lower() if len(ks_parts) > 1 else "major"
                    m21_measure.append(key.Key(tonic, mode))
                    
                events = measure_item.get("events", [])
                if not events:
                    r = note.Rest()
                    r.quarterLength = expected_beats
                    m21_measure.append(r)
                else:
                    current_beats = 0.0
                    for event in events:
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
                        current_beats += dur_val
                        
                    if current_beats < expected_beats - 1e-5:
                        r = note.Rest()
                        r.quarterLength = expected_beats - current_beats
                        m21_measure.append(r)
                        
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
