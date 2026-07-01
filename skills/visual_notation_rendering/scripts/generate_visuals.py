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

def beats_to_time_signature(beats):
    if abs(beats - round(beats)) < 1e-5:
        return f"{int(round(beats))}/4"
    if abs(beats * 2 - round(beats * 2)) < 1e-5:
        return f"{int(round(beats * 2))}/8"
    return f"{int(round(beats * 4))}/16"

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
    parser.add_argument("--tracks", default="", help="Optional comma-separated list of tracks to render")
    parser.add_argument("--format", default="", help="Optional comma-separated list of formats to render (piano_roll, score_plot, musicxml)")
    args = parser.parse_args()

    # Determine paths
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent.parent.parent.resolve()
    
    if args.score_path:
        score_path = Path(args.score_path)
    else:
        score_path = project_root / "skills" / "score_construction" / "assets" / f"score_{args.session_id}.json"
        
    assets_dir = script_dir.parent / "assets"
    piano_roll_path = assets_dir / f"piano_roll_{args.session_id}.png"
    score_plot_path = assets_dir / f"score_plot_{args.session_id}.png"
    musicxml_path = assets_dir / f"score_{args.session_id}.musicxml"

    requested_formats = set()
    if args.format:
        for fmt in args.format.split(","):
            fmt_clean = fmt.strip().lower()
            if fmt_clean in ("musicxml", "score_xml"):
                requested_formats.add("musicxml")
            elif fmt_clean in ("piano_roll", "score_plot"):
                requested_formats.add(fmt_clean)
    else:
        requested_formats = {"piano_roll", "score_plot", "musicxml"}
    
    try:
        if not score_path.is_file():
            raise FileNotFoundError(f"Score state file not found: {score_path}")
            
        with open(score_path, "r", encoding="utf-8") as f:
            state = json.load(f)
            
        parts = state.get("parts", [])
        if not parts:
            raise ValueError("Score has no parts to render.")
            
        if args.tracks:
            selected_specs = [t.strip().lower() for t in args.tracks.split(",") if t.strip()]
            filtered_parts = []
            for part_idx, part in enumerate(parts):
                part_id = part.get("id", "").lower()
                part_name = part.get("name", "").lower()
                track_num_str = str(part_idx + 1)
                
                match = False
                for spec in selected_specs:
                    if spec == track_num_str:
                        match = True
                        break
                    if spec in part_id or spec in part_name:
                        match = True
                        break
                if match:
                    filtered_parts.append(part)
            parts = filtered_parts
            if not parts:
                raise ValueError(f"No tracks matched filter: {args.tracks}")
            
        # Normalize all parts to have the exact same number of measures
        max_measures = max(len(p.get("measures", [])) for p in parts)
        for p in parts:
            curr_len = len(p.get("measures", []))
            if curr_len < max_measures:
                for m_idx in range(curr_len, max_measures):
                    p.setdefault("measures", []).append({
                        "number": m_idx + 1,
                        "events": []
                    })
            
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
        if "piano_roll" in requested_formats or "score_plot" in requested_formats:
            import matplotlib.patheffects as path_effects
            pe = [path_effects.withStroke(linewidth=3, foreground='white')]
            
            fig, ax = plt.subplots(figsize=(10, 5), facecolor='none')
            ax.set_facecolor('none')
            
            t = ax.set_title("Score Piano Roll View (Multi-Part)", fontsize=14, fontweight='bold', pad=15, color='#0F172A')
            t.set_path_effects(pe)
            
            xl = ax.set_xlabel("Time (Beats)", fontsize=11, labelpad=10, color='#0F172A')
            xl.set_path_effects(pe)
            
            yl = ax.set_ylabel("Pitch", fontsize=11, labelpad=10, color='#0F172A')
            yl.set_path_effects(pe)
            
            ax.grid(True, which='both', linestyle=':', color='#CBD5E1', alpha=0.6)
            
            # Beautiful modern palette
            MODERN_PART_COLORS = ['#4F46E5', '#10B981', '#EF4444', '#F59E0B', '#8B5CF6', '#14B8A6']
            
            # Plot horizontal segments for each part
            plotted_parts = set()
            for start, end, midi, pitch, part_idx, part_id in note_data:
                color = MODERN_PART_COLORS[part_idx % len(MODERN_PART_COLORS)]
                label = part_id if part_id not in plotted_parts else ""
                if label:
                    plotted_parts.add(part_id)
                ax.plot([start, end], [midi, midi], color=color, linewidth=8, solid_capstyle='butt', label=label)
                
            ax.set_yticks(sorted_midi)
            ax.set_yticklabels(sorted_labels)
            
            for label in ax.get_xticklabels() + ax.get_yticklabels():
                label.set_color('#0F172A')
                label.set_path_effects(pe)
                
            if len(sorted_midi) == 1:
                ax.set_ylim(sorted_midi[0] - 1, sorted_midi[0] + 1)
            else:
                ax.set_ylim(sorted_midi[0] - 0.5, sorted_midi[-1] + 0.5)
                
            ax.set_xlim(-0.2, max_time + 0.2)
            if plotted_parts:
                ax.legend(loc='upper right', facecolor='#F8FAFC', edgecolor='#CBD5E1', framealpha=0.9)
                
            plt.tight_layout()
            
            if "piano_roll" in requested_formats:
                fig.savefig(piano_roll_path, dpi=150, facecolor='none', transparent=True)
            if "score_plot" in requested_formats:
                fig.savefig(score_plot_path, dpi=150, facecolor='none', transparent=True)
            plt.close(fig)
        
        # 2. music21 MusicXML Export
        if "musicxml" in requested_formats:
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
                    
                    actual_max = measure_max_beats.get(m_num, 0.0)
                    if actual_max > expected_beats:
                        expected_beats = actual_max
                        ts_str = beats_to_time_signature(expected_beats)
                    
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
                
            m21_score.write("musicxml", fp=str(musicxml_path))
        
        # Make relative paths from project root for portability and filter by what exists
        output_data = {
            "status": "success"
        }
        if "piano_roll" in requested_formats and piano_roll_path.is_file():
            output_data["piano_roll"] = piano_roll_path.relative_to(project_root).as_posix()
        if "score_plot" in requested_formats and score_plot_path.is_file():
            output_data["score_plot"] = score_plot_path.relative_to(project_root).as_posix()
        if "musicxml" in requested_formats and musicxml_path.is_file():
            output_data["score_xml"] = musicxml_path.relative_to(project_root).as_posix()
            
        print(json.dumps(output_data, indent=2))
        sys.exit(0)
        
    except Exception as e:
        print(json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()
