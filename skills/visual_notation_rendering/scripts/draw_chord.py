#!/usr/bin/env python3
import sys
import json
import re
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Helper to convert pitch string to MIDI number
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

# Standard Guitar Chord Database (string order: low E, A, D, G, B, high e)
GUITAR_CHORDS = {
    "C": [None, 3, 2, 0, 1, 0],
    "C Major": [None, 3, 2, 0, 1, 0],
    "Cmaj": [None, 3, 2, 0, 1, 0],
    "G": [3, 2, 0, 0, 0, 3],
    "G Major": [3, 2, 0, 0, 0, 3],
    "Gmaj": [3, 2, 0, 0, 0, 3],
    "D": [None, None, 0, 2, 3, 2],
    "D Major": [None, None, 0, 2, 3, 2],
    "Dmaj": [None, None, 0, 2, 3, 2],
    "A": [None, 0, 2, 2, 2, 0],
    "A Major": [None, 0, 2, 2, 2, 0],
    "Amaj": [None, 0, 2, 2, 2, 0],
    "E": [0, 2, 2, 1, 0, 0],
    "E Major": [0, 2, 2, 1, 0, 0],
    "Emaj": [0, 2, 2, 1, 0, 0],
    "F": [1, 3, 3, 2, 1, 1],
    "F Major": [1, 3, 3, 2, 1, 1],
    "Fmaj": [1, 3, 3, 2, 1, 1],
    "Am": [None, 0, 2, 2, 1, 0],
    "A Minor": [None, 0, 2, 2, 1, 0],
    "Amin": [None, 0, 2, 2, 1, 0],
    "Em": [0, 2, 2, 0, 0, 0],
    "E Minor": [0, 2, 2, 0, 0, 0],
    "Emin": [0, 2, 2, 0, 0, 0],
    "Dm": [None, None, 0, 2, 3, 1],
    "D Minor": [None, None, 0, 2, 3, 1],
    "Dmin": [None, None, 0, 2, 3, 1],
    "C7": [None, 3, 2, 3, 1, 0],
    "G7": [3, 2, 0, 0, 0, 1],
    "D7": [None, None, 0, 2, 1, 2],
    "A7": [None, 0, 2, 0, 2, 0],
    "E7": [0, 2, 0, 1, 0, 0],
    "B7": [None, 2, 1, 2, 0, 2],
    "Am7": [None, 0, 2, 0, 1, 0],
    "Dm7": [None, None, 0, 2, 1, 1],
    "Em7": [0, 2, 0, 0, 0, 0],
}

def draw_piano_keyboard(midi_notes, title=""):
    fig, ax = plt.subplots(figsize=(8, 3.5), facecolor='#1e1e24')
    ax.set_facecolor('#1e1e24')
    
    # 2 octaves range: C3 (48) to B4 (71)
    white_keys = [48, 50, 52, 53, 55, 57, 59, 60, 62, 64, 65, 67, 69, 71]
    black_keys = [49, 51, 54, 56, 58, 61, 63, 66, 68, 70]
    
    # Map MIDI value to white key index
    white_to_idx = {val: idx for idx, val in enumerate(white_keys)}
    
    # Render white keys
    for idx, val in enumerate(white_keys):
        rect = patches.Rectangle(
            (idx, 0), 0.96, 4.0,
            edgecolor='#2b2d42', facecolor='#f7f7ff',
            linewidth=1.5
        )
        ax.add_patch(rect)
        
    # Render black keys (drawn on top)
    # Positions are fractional spacing between white keys
    black_positions = {
        49: 0.65, 51: 1.65, 54: 3.65, 56: 4.65, 58: 5.65,
        61: 7.65, 63: 8.65, 66: 10.65, 68: 11.65, 70: 12.65
    }
    
    for val, x in black_positions.items():
        rect = patches.Rectangle(
            (x, 1.4), 0.6, 2.6,
            edgecolor='#1e1e24', facecolor='#2b2d42',
            linewidth=1.2
        )
        ax.add_patch(rect)
        
    # Highlight pressed notes
    highlight_color = '#06d6a0' # Sleek bright green/teal
    for note_val in midi_notes:
        if note_val in white_to_idx:
            # White key: put circle in bottom half
            w_idx = white_to_idx[note_val]
            circle = patches.Circle((w_idx + 0.48, 0.7), 0.28, color=highlight_color, zorder=5)
            ax.add_patch(circle)
            # Label
            ax.text(w_idx + 0.48, 0.7, str(note_val), color='#1e1e24',
                    fontsize=8, fontweight='bold', ha='center', va='center', zorder=6)
        elif note_val in black_positions:
            # Black key: put circle in middle
            bx = black_positions[note_val]
            circle = patches.Circle((bx + 0.3, 2.2), 0.22, color=highlight_color, zorder=5)
            ax.add_patch(circle)
            # Label
            ax.text(bx + 0.3, 2.2, str(note_val), color='#1e1e24',
                    fontsize=7, fontweight='bold', ha='center', va='center', zorder=6)
                    
    # Setup coordinates and remove axes
    ax.set_xlim(-0.2, len(white_keys) + 0.2)
    ax.set_ylim(-0.2, 4.5)
    ax.axis('off')
    
    if title:
        plt.title(title, color='#f7f7ff', fontsize=12, fontweight='bold', pad=10)
        
    plt.tight_layout()
    return fig

def draw_guitar_chord(voicing, chord_name=""):
    fig, ax = plt.subplots(figsize=(4, 5.5), facecolor='#1e1e24')
    ax.set_facecolor('#1e1e24')
    
    # 6 strings vertical lines
    for string_idx in range(6):
        linewidth = 1.0 + (5 - string_idx) * 0.4 # Low strings are thicker
        ax.plot([string_idx, string_idx], [0, 4], color='#8d99ae', linewidth=linewidth, zorder=1)
        
    # 5 frets horizontal lines
    for fret_idx in range(5):
        if fret_idx == 0:
            # The nut (thicker top line)
            ax.plot([-0.1, 5.1], [4, 4], color='#f7f7ff', linewidth=4.0, zorder=2)
        else:
            ax.plot([0, 5], [4 - fret_idx, 4 - fret_idx], color='#8d99ae', linewidth=1.5, zorder=1)
            
    # Draw string labels above nut
    string_labels = ['E', 'A', 'D', 'G', 'B', 'e']
    
    # Voicing details: voicing is standard low E to high e order
    for idx, fret in enumerate(voicing):
        string_x = idx
        if fret is None:
            # Muted string (X)
            ax.text(string_x, 4.3, 'x', color='#ef476f', fontsize=14, fontweight='bold', ha='center', va='center')
        elif fret == 0:
            # Open string (O)
            ax.text(string_x, 4.3, 'o', color='#06d6a0', fontsize=14, fontweight='bold', ha='center', va='center')
        else:
            # Fingered string: place dot on the fretboard
            # Fret y coordinate: 4 - fret + 0.5 (middle of the fret)
            fret_y = 4.5 - fret
            circle = patches.Circle((string_x, fret_y), 0.28, color='#06d6a0', zorder=3)
            ax.add_patch(circle)
            # Add note label or finger label
            ax.text(string_x, fret_y, string_labels[idx], color='#1e1e24', fontsize=9, fontweight='bold', ha='center', va='center', zorder=4)
            
    # Add fret numbers on the left
    for fret_idx in range(1, 5):
        ax.text(-0.6, 4.5 - fret_idx, f"fr {fret_idx}", color='#8d99ae', fontsize=9, ha='center', va='center')
        
    ax.set_xlim(-0.8, 5.8)
    ax.set_ylim(-0.5, 4.8)
    ax.axis('off')
    
    if chord_name:
        plt.title(chord_name, color='#f7f7ff', fontsize=14, fontweight='bold', pad=15)
        
    plt.tight_layout()
    return fig

def main():
    parser = argparse.ArgumentParser(description="Custom chord diagram renderer.")
    parser.add_argument("--pitches", default="", help="Comma-separated pitch names (e.g. C4,E4,G4)")
    parser.add_argument("--instrument", default="piano", choices=["piano", "guitar"], help="Instrument diagram type")
    parser.add_argument("--chord-name", default="", help="Fretboard chord name lookup")
    parser.add_argument("--session-id", required=True, help="Unique ADK runtime session ID")
    args = parser.parse_args()
    
    # Determine save path
    script_dir = Path(__file__).parent.resolve()
    assets_dir = script_dir.parent / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    output_path = assets_dir / f"chord_{args.session_id}.png"
    
    try:
        if args.instrument == "piano":
            # Parse pitches
            pitches_list = [p.strip() for p in args.pitches.split(",") if p.strip()]
            if not pitches_list:
                if not args.chord_name:
                    raise ValueError("Pitches or chord_name are required for piano keyboard rendering.")
                
                # Try to parse the chord name using music21
                import re
                import music21
                name = args.chord_name.strip()
                name = re.sub(r'\b[Mm]ajor\b', '', name)
                name = re.sub(r'\b[Mm]inor\b', 'm', name)
                name = name.replace(' ', '')
                
                try:
                    h = music21.harmony.ChordSymbol(name)
                    root_midi = h.root().midi
                    
                    # Find octave shift to bring the root into range [48, 59]
                    octave_offset = 0
                    if root_midi < 48:
                        while root_midi + octave_offset * 12 < 48:
                            octave_offset += 1
                    elif root_midi > 59:
                        while root_midi + octave_offset * 12 > 59:
                            octave_offset -= 1
                            
                    for p in h.pitches:
                        from music21.pitch import Pitch
                        shifted_p = Pitch(p.midi + octave_offset * 12)
                        pitches_list.append(shifted_p.nameWithOctave)
                except Exception as e:
                    raise ValueError(f"Could not resolve chord name '{args.chord_name}' to piano pitches: {e}")
                
            midi_notes = []
            for p in pitches_list:
                midi = pitch_to_midi(p)
                if midi:
                    midi_notes.append(midi)
                    
            title = args.chord_name or f"Piano Triad: {', '.join(pitches_list)}"
            fig = draw_piano_keyboard(midi_notes, title=title)
            fig.savefig(output_path, dpi=120, facecolor='#1e1e24')
            plt.close(fig)
            
        elif args.instrument == "guitar":
            # Lookup chord voicing
            name = args.chord_name.strip()
            if not name:
                raise ValueError("Chord name is required for guitar fretboard lookup.")
                
            # Try to match chord name case insensitively
            voicing = None
            for key_name, val in GUITAR_CHORDS.items():
                if key_name.lower() == name.lower():
                    voicing = val
                    break
                    
            if not voicing:
                # Default to C Major if not found
                voicing = GUITAR_CHORDS["C Major"]
                chord_title = f"{name} (Voicing Default)"
            else:
                chord_title = name
                
            fig = draw_guitar_chord(voicing, chord_name=chord_title)
            fig.savefig(output_path, dpi=120, facecolor='#1e1e24')
            plt.close(fig)
            
        # Output success JSON
        print(json.dumps({
            "status": "success",
            "action": "draw-chord",
            "instrument": args.instrument,
            "chord_name": args.chord_name,
            "output_path": str(output_path.relative_to(script_dir.parent.parent.parent.resolve()).as_posix())
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
