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
            
        # Check file size (limit to 5 MB)
        max_size_bytes = 5 * 1024 * 1024  # 5 MB
        if file_path.stat().st_size > max_size_bytes:
            raise ValueError(f"MIDI file is too large ({file_path.stat().st_size / (1024 * 1024):.1f} MB). Maximum allowed size is 5.0 MB.")
            
        # Parse MIDI using pretty_midi with a fallback to mido
        try:
            pm = pretty_midi.PrettyMIDI(str(file_path))
            track_count = len(pm.instruments)
            note_count = sum(len(inst.notes) for inst in pm.instruments)
            tempo_times, tempo_bpms = pm.get_tempo_changes()
            global_tempo = float(tempo_bpms[0]) if len(tempo_bpms) > 0 else 120.0
            
            instruments_info = []
            for i, inst in enumerate(pm.instruments):
                inst_name = pretty_midi.program_to_instrument_name(inst.program) if not inst.is_drum else "Drums / Percussion"
                instruments_info.append({
                    "track_index": int(i),
                    "name": inst.name.strip() if inst.name else f"Track {i + 1}",
                    "program": int(inst.program),
                    "instrument": inst_name,
                    "is_drum": bool(inst.is_drum),
                    "note_count": int(len(inst.notes))
                })
        except Exception as pm_err:
            try:
                import mido
                mid = mido.MidiFile(str(file_path))
                track_count = len(mid.tracks)
                
                global_tempo = 120.0
                note_count = 0
                track_note_counts = [0] * track_count
                track_programs = [0] * track_count
                track_is_drum = [False] * track_count
                track_names = [""] * track_count
                
                for t_idx, track in enumerate(mid.tracks):
                    for msg in track:
                        if msg.type == "set_tempo":
                            global_tempo = float(mido.tempo2bpm(msg.tempo))
                        elif msg.type == "note_on" and msg.velocity > 0:
                            note_count += 1
                            track_note_counts[t_idx] += 1
                            if hasattr(msg, "channel") and msg.channel == 9:
                                track_is_drum[t_idx] = True
                        elif msg.type == "program_change":
                            track_programs[t_idx] = msg.program
                        elif msg.type == "track_name":
                            track_names[t_idx] = msg.name
                            
                instruments_info = []
                for i in range(track_count):
                    prog = track_programs[i]
                    is_drum = track_is_drum[i]
                    inst_name = pretty_midi.program_to_instrument_name(prog) if not is_drum else "Drums / Percussion"
                    instruments_info.append({
                        "track_index": int(i),
                        "name": track_names[i].strip() if track_names[i] else f"Track {i + 1}",
                        "program": int(prog),
                        "instrument": inst_name,
                        "is_drum": bool(is_drum),
                        "note_count": int(track_note_counts[i])
                    })
            except Exception as mido_err:
                raise ValueError(
                    f"Failed to parse MIDI file. It may be corrupt or invalid.\n"
                    f"pretty_midi error: {pm_err}\n"
                    f"mido error: {mido_err}"
                )
            
        result = {
            "status": "success",
            "file_path": args.file_path,
            "track_count": track_count,
            "tempo": global_tempo,
            "note_count": note_count,
            "instruments": instruments_info
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
