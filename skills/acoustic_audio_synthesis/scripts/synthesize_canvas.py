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
    "whole": 4.0,
    "half": 2.0,
    "quarter": 1.0,
    "eighth": 0.5,
    "sixteenth": 0.25
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
    parser.add_argument("--canvas-path", help="Path to the canvas state JSON file")
    parser.add_argument("--session-id", type=str, required=True, help="Unique ADK runtime session ID")
    args = parser.parse_args()

    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent.parent.parent.resolve()
    
    if args.canvas_path:
        canvas_path = Path(args.canvas_path)
    else:
        canvas_path = project_root / "skills" / "score_construction" / "assets" / f"canvas_{args.session_id}.json"
        
    assets_dir = script_dir.parent / "assets"
    output_file = assets_dir / f"score_{args.session_id}.wav"
    
    try:
        if not canvas_path.is_file():
            raise FileNotFoundError(f"Canvas state file not found: {canvas_path}")
            
        with open(canvas_path, "r", encoding="utf-8") as f:
            state = json.load(f)
            
        parts = state.get("parts", [])
        if not parts:
            raise ValueError("Canvas has no parts to synthesize.")
            
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        sample_rate = 44100
        volume = 0.5
        decay_rate = 3.0
        
        # Calculate maximum duration across all parts
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
            raise ValueError("Canvas has no notes to synthesize.")
            
        # Allocate master mixing array (1 beat = 0.5 seconds at 120 BPM)
        total_seconds = max_beats * 0.5
        num_samples = int(total_seconds * sample_rate) + 1000  # add buffer for decay tail
        mixed_audio = [0.0] * num_samples
        
        for part in parts:
            current_beat = 0.0
            for measure in part.get("measures", []):
                for event in measure.get("events", []):
                    dur_str = event.get("duration", "quarter").lower()
                    dur_beats = DURATION_MAP.get(dur_str, 1.0)
                    dur_seconds = dur_beats * 0.5
                    event_samples = int(dur_seconds * sample_rate)
                    
                    pitches = event.get("pitches", ["rest"])
                    
                    if not pitches or "rest" in [p.lower() for p in pitches]:
                        current_beat += dur_beats
                        continue
                        
                    start_sample = int(current_beat * 0.5 * sample_rate)
                    
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
                    
        # Normalize and pack audio data
        audio_data = bytearray()
        max_val = max(abs(x) for x in mixed_audio) if mixed_audio else 0.0
        
        for val in mixed_audio:
            if max_val > 0.0:
                sample = int((val / max_val) * 32767.0 * volume)
            else:
                sample = 0
            sample = max(-32768, min(32767, sample))
            audio_data.extend(struct.pack('<h', sample))
            
        # Write WAV file
        with wave.open(str(output_file), 'wb') as wav_file:
            wav_file.setnchannels(1)      # Mono
            wav_file.setsampwidth(2)     # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
            
        abs_path = str(output_file.resolve().as_posix())
        print(json.dumps({
            "status": "success",
            "audio_path": abs_path
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
