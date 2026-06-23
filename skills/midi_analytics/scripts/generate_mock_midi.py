#!/usr/bin/env python3
from music21 import stream, note, tempo
from pathlib import Path

def main():
    # Create a stream
    s = stream.Stream()
    
    # Set the tempo to exactly 120 BPM
    s.append(tempo.MetronomeMark(number=120))
    
    # Generate exactly 256 notes to satisfy BDD specifications
    for i in range(256):
        n = note.Note("C4")
        n.quarterLength = 0.25  # Sixteenth notes
        s.append(n)
        
    # Set paths
    script_dir = Path(__file__).parent.resolve()
    assets_dir = script_dir.parent / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    output_file = assets_dir / "sample.mid"
    
    # Write MIDI file
    s.write("midi", fp=str(output_file))
    print(f"Successfully generated mock MIDI file with 256 notes and 120 BPM at: {output_file}")

if __name__ == "__main__":
    main()
