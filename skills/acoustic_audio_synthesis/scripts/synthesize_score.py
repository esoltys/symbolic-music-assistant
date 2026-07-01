#!/usr/bin/env python3
import sys
import json
import re
import math
import struct
import wave
import argparse
from pathlib import Path

DURATION_MAP = {
    "dotted whole": 6.0,
    "whole": 4.0,
    "dotted half": 3.0,
    "half": 2.0,
    "dotted quarter": 1.5,
    "quarter": 1.0,
    "dotted eighth": 0.75,
    "eighth": 0.5,
    "dotted sixteenth": 0.375,
    "sixteenth": 0.25,
    "dotted thirty-second": 0.1875,
    "thirty-second": 0.125,
    # Aliases
    "dotted-whole": 6.0,
    "dotted-half": 3.0,
    "dotted-quarter": 1.5,
    "dotted-eighth": 0.75,
    "dotted-sixteenth": 0.375,
    "dotted 16th": 0.375,
    "dotted-16th": 0.375,
    "16th": 0.25,
    "dotted-thirty-second": 0.1875,
    "dotted 32nd": 0.1875,
    "dotted-32nd": 0.1875,
    "32nd": 0.125
}

def pitch_to_midi(pitch_str):
    if pitch_str.lower() == "rest":
        return None
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

def midi_to_freq(midi_num):
    if midi_num is None:
        return 0.0
    return 440.0 * (2.0 ** ((midi_num - 69) / 12.0))

def main():
    parser = argparse.ArgumentParser(description="Synthesize hierarchical score state to WAV audio.")
    parser.add_argument("--score-path", help="Path to the score state JSON file")
    parser.add_argument("--session-id", type=str, required=True, help="Unique ADK runtime session ID")
    parser.add_argument("--tracks", help="Comma-separated track IDs, names, or 1-based indices to play/synthesize")
    parser.add_argument("--soundfont", help="Soundfont filename (e.g. 'TimGM6mb.sf2' or 'SalamanderGrandPiano-V3+20200602.sf2') from the soundfonts/ directory")
    args = parser.parse_args()

    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent.parent.parent.resolve()
    
    if args.score_path:
        score_path = Path(args.score_path)
    else:
        score_path = project_root / "skills" / "score_construction" / "assets" / f"score_{args.session_id}.json"
        
    assets_dir = script_dir.parent / "assets"
    output_file = assets_dir / f"score_{args.session_id}.wav"
    
    try:
        if not score_path.is_file():
            raise FileNotFoundError(f"Score state file not found: {score_path}")
            
        with open(score_path, "r", encoding="utf-8") as f:
            state = json.load(f)
            
        parts = state.get("parts", [])
        if not parts:
            raise ValueError("Score has no parts to synthesize.")
            
        # Filter parts if --tracks is specified
        if args.tracks:
            selected_track_specs = [t.strip().lower() for t in args.tracks.split(",") if t.strip()]
            filtered_parts = []
            
            for part_idx, part in enumerate(parts):
                part_id = part.get("id", "").lower()
                part_name = part.get("name", "").lower()
                track_number_str = str(part_idx + 1)
                
                # Check if this part matches any of the specified tracks
                match = False
                for spec in selected_track_specs:
                    # Match by 1-based index (e.g. "1", "2")
                    if spec == track_number_str:
                        match = True
                        break
                    # Match by track ID or name (e.g. "piano", "melody")
                    if spec in part_id or spec in part_name:
                        match = True
                        break
                    # Support ranges like "7-8"
                    if "-" in spec:
                        try:
                            start, end = map(int, spec.split("-"))
                            if start <= part_idx + 1 <= end:
                                match = True
                                break
                        except ValueError:
                            pass
                            
                if match:
                    filtered_parts.append(part)
                    
            if not filtered_parts:
                raise ValueError(f"No tracks matched the specifications: {args.tracks}")
            parts = filtered_parts

        assets_dir.mkdir(parents=True, exist_ok=True)
        
        sample_rate = 44100
        volume = 0.5
        decay_rate = 3.0
        
        # Build tempo/time converter
        tempos = state.get("tempos", [])
        tempos = sorted(tempos, key=lambda x: x["offset"])
        if not tempos or tempos[0]["offset"] > 0:
            tempos.insert(0, {"offset": 0.0, "bpm": 120.0})
            
        # Precompute accumulated times at each boundary
        accumulated_times = [0.0]
        for i in range(len(tempos) - 1):
            dt = tempos[i+1]["offset"] - tempos[i]["offset"]
            seconds_per_beat = 60.0 / tempos[i]["bpm"]
            accumulated_times.append(accumulated_times[-1] + dt * seconds_per_beat)
            
        def beats_to_seconds(beat_offset):
            for i in range(len(tempos) - 1):
                if tempos[i]["offset"] <= beat_offset < tempos[i+1]["offset"]:
                    dt = beat_offset - tempos[i]["offset"]
                    return accumulated_times[i] + dt * (60.0 / tempos[i]["bpm"])
            dt = beat_offset - tempos[-1]["offset"]
            return accumulated_times[-1] + dt * (60.0 / tempos[-1]["bpm"])
        
        # Resolve soundfont: use --soundfont if provided, otherwise prefer TimGM6mb.sf2,
        # then fall back to any .sf2 found in the soundfonts/ directory.
        sf2_dir = project_root / "soundfonts"
        sf2_path = None
        if sf2_dir.is_dir():
            if args.soundfont:
                # Security: only accept a bare filename (no path separators) so the
                # resolved file is always inside soundfonts/
                sf2_name = Path(args.soundfont).name  # strips any directory components
                candidate = sf2_dir / sf2_name
                if candidate.is_file():
                    sf2_path = candidate
                else:
                    raise FileNotFoundError(
                        f"Soundfont '{sf2_name}' not found in soundfonts/ directory. "
                        f"Run list_soundfonts to see available options."
                    )
            else:
                preferred = sf2_dir / "TimGM6mb.sf2"
                if preferred.is_file():
                    sf2_path = preferred
                else:
                    for f in sf2_dir.glob("*.sf2"):
                        sf2_path = f
                        break

        use_tinysoundfont = False
        if sf2_path is not None:
            try:
                import tinysoundfont
                use_tinysoundfont = True
            except ImportError:
                pass

        if use_tinysoundfont:
            # tinysoundfont synthesis (stereo)
            part_channels = {}
            next_melodic_channel = 0
            for part_idx, part in enumerate(parts):
                is_percussion = part.get("is_percussion", False)
                if is_percussion:
                    part_channels[part_idx] = 9
                else:
                    if next_melodic_channel == 9:
                        next_melodic_channel += 1
                    part_channels[part_idx] = next_melodic_channel % 16
                    next_melodic_channel += 1

            midi_events = []
            for part_idx, part in enumerate(parts):
                channel = part_channels[part_idx]
                current_beat = 0.0
                for measure in part.get("measures", []):
                    for event in measure.get("events", []):
                        dur_str = event.get("duration", "quarter").lower()
                        dur_beats = DURATION_MAP.get(dur_str, 1.0)
                        
                        pitches = event.get("pitches", ["rest"])
                        if pitches and "rest" not in [p.lower() for p in pitches]:
                            start_sec = beats_to_seconds(current_beat)
                            end_sec = beats_to_seconds(current_beat + dur_beats)
                            for pitch_str in pitches:
                                midi_num = pitch_to_midi(pitch_str)
                                if midi_num is not None:
                                    midi_events.append((start_sec, 'on', channel, midi_num))
                                    midi_events.append((end_sec, 'off', channel, midi_num))
                        current_beat += dur_beats
            
            midi_events.sort(key=lambda e: e[0])
            
            synth = tinysoundfont.Synth()
            sfid = synth.sfload(str(sf2_path))
            for channel in range(16):
                synth.program_select(channel, sfid, 0, 0)
                
            for part_idx, part in enumerate(parts):
                channel = part_channels[part_idx]
                program = part.get("program", 0)
                is_percussion = part.get("is_percussion", False)
                bank = 128 if is_percussion else 0
                synth.program_select(channel, sfid, bank, program)
            
            audio_data = bytearray()
            current_sample = 0
            
            for event in midi_events:
                event_sec, ev_type, channel, midi_num = event
                event_sample = int(event_sec * sample_rate)
                
                if event_sample > current_sample:
                    delta_samples = event_sample - current_sample
                    buf = synth.generate(delta_samples)
                    fview = buf.cast('f')
                    for val in fview:
                        sample = int(val * 32767.0 * volume)
                        sample = max(-32768, min(32767, sample))
                        audio_data.extend(struct.pack('<h', sample))
                    current_sample = event_sample
                
                if ev_type == 'on':
                    synth.noteon(channel, midi_num, 100)
                else:
                    synth.noteoff(channel, midi_num)
            
            # Render a 2.0-second decay tail
            tail_samples = int(2.0 * sample_rate)
            buf = synth.generate(tail_samples)
            fview = buf.cast('f')
            for val in fview:
                sample = int(val * 32767.0 * volume)
                sample = max(-32768, min(32767, sample))
                audio_data.extend(struct.pack('<h', sample))
                
            channels_count = 2
        else:
            # Fallback pure-python sine wave synthesis (mono)
            max_beats = 0.0
            for part in parts:
                part_beats = 0.0
                for measure in part.get("measures", []):
                    for event in measure.get("events", []):
                        dur_str = event.get("duration", "quarter").lower()
                        part_beats += DURATION_MAP.get(dur_str, 1.0)
                if part_beats > max_beats:
                    max_beats = part_beats
                    
            if max_beats == 0.0:
                raise ValueError("Score has no notes to synthesize.")
                
            total_seconds = beats_to_seconds(max_beats)
            num_samples = int(total_seconds * sample_rate) + 1000
            mixed_audio = [0.0] * num_samples
            
            for part in parts:
                current_beat = 0.0
                for measure in part.get("measures", []):
                    for event in measure.get("events", []):
                        dur_str = event.get("duration", "quarter").lower()
                        dur_beats = DURATION_MAP.get(dur_str, 1.0)
                        start_sec = beats_to_seconds(current_beat)
                        end_sec = beats_to_seconds(current_beat + dur_beats)
                        dur_seconds = end_sec - start_sec
                        event_samples = int(dur_seconds * sample_rate)
                        
                        pitches = event.get("pitches", ["rest"])
                        if not pitches or "rest" in [p.lower() for p in pitches]:
                            current_beat += dur_beats
                            continue
                            
                        start_sample = int(start_sec * sample_rate)
                        for pitch_str in pitches:
                            try:
                                midi_num = pitch_to_midi(pitch_str)
                                freq = midi_to_freq(midi_num)
                                if freq > 0.0:
                                    for i in range(event_samples):
                                        t = i / sample_rate
                                        val = math.sin(2.0 * math.pi * freq * t) * math.exp(-decay_rate * t)
                                        idx = start_sample + i
                                        if idx < len(mixed_audio):
                                            mixed_audio[idx] += val
                            except ValueError:
                                pass
                        current_beat += dur_beats
                        
            audio_data = bytearray()
            max_val = max(abs(x) for x in mixed_audio) if mixed_audio else 0.0
            for val in mixed_audio:
                if max_val > 0.0:
                    sample = int((val / max_val) * 32767.0 * volume)
                else:
                    sample = 0
                sample = max(-32768, min(32767, sample))
                audio_data.extend(struct.pack('<h', sample))
                
            channels_count = 1
            
        # Write WAV file
        with wave.open(str(output_file), 'wb') as wav_file:
            wav_file.setnchannels(channels_count)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
            
        rel_path = output_file.relative_to(project_root).as_posix()
        print(json.dumps({
            "status": "success",
            "audio_path": rel_path,
            "soundfont": sf2_path.name if sf2_path else "sine-wave fallback"
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
