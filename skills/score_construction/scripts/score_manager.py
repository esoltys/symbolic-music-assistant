#!/usr/bin/env python3
import sys
import json
import argparse
from pathlib import Path
from music21 import stream, note, chord, clef, meter, key as m21_key, pitch, converter

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

def transpose_pitch_string(pitch_str, semitones):
    if pitch_str.lower() == "rest" or not pitch_str:
        return "rest"
    
    # Split chord if it's comma-separated
    pitches = [p.strip() for p in pitch_str.split(",") if p.strip()]
    transposed_pitches = []
    for p in pitches:
        m21_pitch = pitch.Pitch(p)
        transposed_pitch = m21_pitch.transpose(semitones)
        transposed_pitches.append(transposed_pitch.nameWithOctave)
    return ",".join(transposed_pitches)

def get_duration_name(quarter_length):
    closest_name = "quarter"
    closest_diff = float("inf")
    for name, val in DURATION_MAP.items():
        diff = abs(quarter_length - val)
        if diff < closest_diff:
            closest_diff = diff
            closest_name = name
    return closest_name

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

    # transpose sub-command
    transpose_parser = subparsers.add_parser("transpose", help="Transpose the active score.")
    transpose_parser.add_argument("--semitones", type=int, required=True, help="Number of semitones to transpose (e.g., 2, -3)")
    transpose_parser.add_argument("--session-id", required=True, help="Unique ADK runtime session ID")

    # export-midi sub-command
    export_parser = subparsers.add_parser("export-midi", help="Export the active score to a MIDI file.")
    export_parser.add_argument("--session-id", required=True, help="Unique ADK runtime session ID")

    # import-midi sub-command
    import_parser = subparsers.add_parser("import-midi", help="Import a MIDI file into the active score state.")
    import_parser.add_argument("--midi-path", required=True, help="Path to the external MIDI file")
    import_parser.add_argument("--session-id", required=True, help="Unique ADK runtime session ID")

    # assign-instrument sub-command
    assign_parser = subparsers.add_parser("assign-instrument", help="Assign an instrument to a track.")
    assign_parser.add_argument("--part-id", required=True, help="ID of the part/track (e.g. 'melody')")
    assign_parser.add_argument("--program", type=int, required=True, help="MIDI program number (0-127)")
    assign_parser.add_argument("--percussion", action="store_true", help="Set track as unpitched percussion")
    assign_parser.add_argument("--session-id", required=True, help="Unique ADK runtime session ID")

    # set-tempo sub-command
    tempo_parser = subparsers.add_parser("set-tempo", help="Set/change tempo at a specific beat offset.")
    tempo_parser.add_argument("--bpm", type=float, required=True, help="Tempo in beats per minute")
    tempo_parser.add_argument("--offset", type=float, default=0.0, help="Beat offset from start (default 0.0)")
    tempo_parser.add_argument("--session-id", required=True, help="Unique ADK runtime session ID")

    args = parser.parse_args()

    # Determine paths
    script_dir = Path(__file__).parent.resolve()
    assets_dir = script_dir.parent / "assets"
    state_file = assets_dir / f"score_{args.session_id}.json"

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

        elif args.command == "transpose":
            if not state_file.is_file():
                raise FileNotFoundError("Score has not been initialized yet.")
                
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                
            semitones = args.semitones
            
            # Transpose key signature
            ks_str = state.get("key_signature", "C Major")
            ks_parts = ks_str.strip().split()
            tonic = ks_parts[0]
            mode = ks_parts[1].lower() if len(ks_parts) > 1 else "major"
            
            k = m21_key.Key(tonic, mode)
            k_transposed = k.transpose(semitones)
            new_key_sig = f"{k_transposed.tonic.name} {k_transposed.mode.capitalize()}"
            state["key_signature"] = new_key_sig
            
            # Transpose all events in all parts
            for part in state.get("parts", []):
                for measure in part.get("measures", []):
                    for event in measure.get("events", []):
                        pitches = event.get("pitches", ["rest"])
                        if pitches and "rest" not in [p.lower() for p in pitches]:
                            transposed_pitches = []
                            for p in pitches:
                                m21_pitch = pitch.Pitch(p)
                                transposed_pitch = m21_pitch.transpose(semitones)
                                transposed_pitches.append(transposed_pitch.nameWithOctave)
                            event["pitches"] = transposed_pitches
            
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
                
            print(json.dumps({
                "status": "success",
                "action": "transpose",
                "semitones": semitones,
                "new_key_signature": new_key_sig
            }, indent=2))
            sys.exit(0)

        elif args.command == "export-midi":
            if not state_file.is_file():
                raise FileNotFoundError("Score has not been initialized yet.")
                
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                
            # Construct music21 score
            m21_score = stream.Score()
            ks_str = state.get("key_signature", "C Major")
            time_signatures = state.get("time_signatures", [{"measure": 1, "ratio": state.get("time_signature", "4/4")}])
            
            # Precompute the max duration of each measure across all parts to handle missing/incomplete time signatures
            measure_max_beats = {}
            for part in state.get("parts", []):
                for measure_item in part.get("measures", []):
                    m_num = measure_item.get("number")
                    events = measure_item.get("events", [])
                    beats = sum(DURATION_MAP.get(e.get("duration", "quarter").lower(), 1.0) for e in events)
                    if m_num is not None:
                        measure_max_beats[m_num] = max(measure_max_beats.get(m_num, 0.0), beats)

            for part_idx, part in enumerate(state.get("parts", [])):
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
                        m21_measure.append(m21_key.Key(tonic, mode))
                        
                    events = measure_item.get("events", [])
                    if not events:
                        # Empty measure: pad with a full-measure rest
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
                            
                        # Pad incomplete measure
                        if current_beats < expected_beats - 1e-5:
                            r = note.Rest()
                            r.quarterLength = expected_beats - current_beats
                            m21_measure.append(r)
                            
                    m21_part.append(m21_measure)
                m21_score.append(m21_part)
                
            midi_path = assets_dir / f"score_{args.session_id}.mid"
            m21_score.write("midi", fp=str(midi_path))
            
            project_root = script_dir.parent.parent.parent.resolve()
            rel_midi_path = midi_path.relative_to(project_root).as_posix()
            
            print(json.dumps({
                "status": "success",
                "action": "export-midi",
                "midi_path": rel_midi_path
            }, indent=2))
            sys.exit(0)

        elif args.command == "import-midi":
            midi_file_path = Path(args.midi_path)
            if not midi_file_path.is_file():
                raise FileNotFoundError(f"MIDI file not found: {args.midi_path}")
                
            # Parse MIDI using music21
            s = converter.parse(str(midi_file_path))
            
            # Find time signature
            ts_str = "4/4"
            ts_el = list(s.recurse().getElementsByClass(meter.TimeSignature))
            if ts_el:
                ts_str = ts_el[0].ratioString
                
            # Find key signature
            ks_str = "C Major"
            ks_el = list(s.recurse().getElementsByClass(m21_key.Key))
            if ks_el:
                ks_str = f"{ks_el[0].tonic.name} {ks_el[0].mode.capitalize()}"
                
            # Find all metronome marks / tempo changes
            from music21 import tempo
            tempos_list = []
            metronome_marks = list(s.recurse().getElementsByClass(tempo.MetronomeMark))
            for mm in metronome_marks:
                tempos_list.append({
                    "offset": mm.offset,
                    "bpm": float(mm.number)
                })
                
            if not tempos_list:
                tempos_list = [{"offset": 0.0, "bpm": 120.0}]
            else:
                tempos_list = sorted(tempos_list, key=lambda x: x["offset"])

            parts_list = []
            parts = list(s.getElementsByClass(stream.Part))
            if not parts:
                parts = [s]
                
            for part_idx, part in enumerate(parts):
                part_id = part.id
                if not part_id or isinstance(part_id, int):
                    part_id = f"part_{part_idx}"
                else:
                    part_id = str(part_id)
                    
                part_name = part.partName if hasattr(part, 'partName') and part.partName else part_id.capitalize()
                
                # Determine instrument program and percussion status
                from music21 import instrument
                program = 0
                is_percussion = False
                instruments = list(part.recurse().getElementsByClass(instrument.Instrument))
                if instruments:
                    for ins in instruments:
                        if ins.midiProgram is not None:
                            program = ins.midiProgram
                        if isinstance(ins, instrument.UnpitchedPercussion):
                            is_percussion = True
                
                # Determine clef
                clef_str = "treble"
                clef_el = list(part.recurse().getElementsByClass(clef.Clef))
                if clef_el:
                    if isinstance(clef_el[0], clef.BassClef):
                        clef_str = "bass"
                        
                measures_list = []
                measures = list(part.getElementsByClass(stream.Measure))
                if not measures:
                    part.makeMeasures(inPlace=True)
                    measures = list(part.getElementsByClass(stream.Measure))
                    
                for measure_idx, measure in enumerate(measures):
                    events = []
                    measure_elements = list(measure.recurse().getElementsByClass([note.Note, chord.Chord, note.Rest]))
                    for el in measure_elements:
                        dur_name = get_duration_name(el.quarterLength)
                        if isinstance(el, note.Note):
                            pitches = [el.pitch.nameWithOctave]
                        elif isinstance(el, chord.Chord):
                            pitches = [p.nameWithOctave for p in el.pitches]
                        else:  # Rest
                            pitches = ["rest"]
                        events.append({
                            "pitches": pitches,
                            "duration": dur_name
                        })
                    measures_list.append({
                        "number": measure.number if measure.number else measure_idx + 1,
                        "events": events
                    })
                    
                parts_list.append({
                    "id": part_id,
                    "name": part_name,
                    "clef": clef_str,
                    "program": program,
                    "is_percussion": is_percussion,
                    "measures": measures_list
                })
                
            state = {
                "time_signature": ts_str,
                "key_signature": ks_str,
                "tempos": tempos_list,
                "parts": parts_list
            }
            
            assets_dir.mkdir(parents=True, exist_ok=True)
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
                
            # Check for uncertain parts (defaulted to program 0 but name doesn't contain 'piano' or 'keyboard')
            uncertain_parts = []
            for part in parts_list:
                name_lower = part["name"].lower()
                if part["program"] == 0 and "piano" not in name_lower and "keyboard" not in name_lower:
                    uncertain_parts.append({
                        "id": part["id"],
                        "name": part["name"]
                    })

            print(json.dumps({
                "status": "success",
                "action": "import-midi",
                "time_signature": ts_str,
                "key_signature": ks_str,
                "parts_count": len(parts_list),
                "imported_parts": [{"id": p["id"], "name": p["name"], "program": p["program"], "is_percussion": p["is_percussion"]} for p in parts_list],
                "uncertain_parts": uncertain_parts
            }, indent=2))
            sys.exit(0)

        elif args.command == "assign-instrument":
            if not state_file.is_file():
                raise FileNotFoundError("Score has not been initialized yet. Run 'init' or 'import-midi' first.")
                
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                
            part_id = args.part_id.strip()
            part = None
            for p in state.get("parts", []):
                if p["id"] == part_id:
                    part = p
                    break
                    
            if part is None:
                raise ValueError(f"Part ID '{part_id}' not found in active score.")
                
            part["program"] = args.program
            part["is_percussion"] = args.percussion
            
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
                
            print(json.dumps({
                "status": "success",
                "action": "assign-instrument",
                "part_id": part_id,
                "program": args.program,
                "is_percussion": args.percussion
            }, indent=2))
            sys.exit(0)

        elif args.command == "set-tempo":
            if not state_file.is_file():
                raise FileNotFoundError("Score has not been initialized yet. Run 'init' or 'import-midi' first.")
                
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                
            if "tempos" not in state:
                state["tempos"] = []
                
            bpm = args.bpm
            offset = args.offset
            updated = False
            for t in state["tempos"]:
                if abs(t["offset"] - offset) < 1e-5:
                    t["bpm"] = bpm
                    updated = True
                    break
            if not updated:
                state["tempos"].append({"offset": offset, "bpm": bpm})
                
            state["tempos"] = sorted(state["tempos"], key=lambda x: x["offset"])
            
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
                
            print(json.dumps({
                "status": "success",
                "action": "set-tempo",
                "bpm": bpm,
                "offset": offset
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
