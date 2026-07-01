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

# Standard Guitar Chord Shapes Database (offsets from root fret on string 5 or 6)
# String indices: 0 (low E), 1 (A), 2 (D), 3 (G), 4 (B), 5 (high e)
SHAPES_S6 = {
    "major": {0: 0, 1: 2, 2: 2, 3: 1, 4: 0, 5: 0},
    "minor": {0: 0, 1: 2, 2: 2, 3: 0, 4: 0, 5: 0},
    "7": {0: 0, 1: 2, 2: 0, 3: 1, 4: 0, 5: 0},
    "m7": {0: 0, 1: 2, 2: 0, 3: 0, 4: 0, 5: 0},
    "maj7": {0: 0, 1: 2, 2: 1, 3: 1, 4: 0, 5: 0},
    "9": {0: 0, 1: -1, 2: 0, 3: 0, 4: 0},
}

SHAPES_S5 = {
    "major": {1: 0, 2: 2, 3: 2, 4: 2, 5: 0},
    "minor": {1: 0, 2: 2, 3: 2, 4: 1, 5: 0},
    "7": {1: 0, 2: 2, 3: 0, 4: 2, 5: 0},
    "m7": {1: 0, 2: 2, 3: 0, 4: 1, 5: 0},
    "maj7": {1: 0, 2: 2, 3: 1, 4: 2, 5: 0},
    "9": {1: 0, 2: -1, 3: 0, 4: 0, 5: 0},
}

OPEN_CHORDS = {
    "C": [None, 3, 2, 0, 1, 0],
    "C major": [None, 3, 2, 0, 1, 0],
    "C7": [None, 3, 2, 3, 1, 0],
    "Cmaj7": [None, 3, 2, 0, 0, 0],
    "C9": [None, 3, 2, 3, 3, 3],
    
    "A": [None, 0, 2, 2, 2, 0],
    "A major": [None, 0, 2, 2, 2, 0],
    "Am": [None, 0, 2, 2, 1, 0],
    "A minor": [None, 0, 2, 2, 1, 0],
    "A7": [None, 0, 2, 0, 2, 0],
    "Am7": [None, 0, 2, 0, 1, 0],
    "Amaj7": [None, 0, 2, 1, 2, 0],
    "A9": [None, 0, 2, 4, 2, 3],
    
    "G": [3, 2, 0, 0, 0, 3],
    "G major": [3, 2, 0, 0, 0, 3],
    "Gm": [3, 5, 5, 3, 3, 3],
    "G7": [3, 2, 0, 0, 0, 1],
    "Gm7": [3, 5, 3, 3, 3, 3],
    "Gmaj7": [3, 2, 0, 0, 0, 2],
    "G9": [3, 2, 0, 2, 0, 1],
    
    "E": [0, 2, 2, 1, 0, 0],
    "E major": [0, 2, 2, 1, 0, 0],
    "Em": [0, 2, 2, 0, 0, 0],
    "E minor": [0, 2, 2, 0, 0, 0],
    "E7": [0, 2, 0, 1, 0, 0],
    "Em7": [0, 2, 0, 0, 0, 0],
    "Emaj7": [0, 2, 1, 1, 0, 0],
    "E9": [0, 2, 0, 1, 0, 2],
    
    "D": [None, None, 0, 2, 3, 2],
    "D major": [None, None, 0, 2, 3, 2],
    "Dm": [None, None, 0, 2, 3, 1],
    "D minor": [None, None, 0, 2, 3, 1],
    "D7": [None, None, 0, 2, 1, 2],
    "Dm7": [None, None, 0, 2, 1, 1],
    "Dmaj7": [None, None, 0, 2, 2, 2],
    "D9": [None, None, 0, 2, 1, 0],
}

def get_guitar_voicing(chord_name: str) -> list:
    name = chord_name.strip()
    
    for key, val in OPEN_CHORDS.items():
        if key.lower() == name.lower():
            return val
            
    match = re.match(r'^([A-G][b#]?)(.*)$', name)
    if not match:
        raise ValueError(f"Invalid chord name format: {name}")
        
    root, quality = match.groups()
    quality = quality.strip().lower()
    
    if quality in ["", "major", "maj"]:
        q_type = "major"
    elif quality in ["m", "minor", "min"]:
        q_type = "minor"
    elif quality in ["7", "dom7"]:
        q_type = "7"
    elif quality in ["m7", "min7"]:
        q_type = "m7"
    elif quality in ["maj7", "major7"]:
        q_type = "maj7"
    elif quality in ["9", "dom9"]:
        q_type = "9"
    else:
        q_type = "major"
        
    ROOT_FRETS_S6 = {'E': 0, 'F': 1, 'F#': 2, 'Gb': 2, 'G': 3, 'G#': 4, 'Ab': 4, 'A': 5, 'A#': 6, 'Bb': 6, 'B': 7, 'C': 8, 'C#': 9, 'Db': 9, 'D': 10, 'D#': 11, 'Eb': 11}
    ROOT_FRETS_S5 = {'A': 0, 'A#': 1, 'Bb': 1, 'B': 2, 'C': 3, 'C#': 4, 'Db': 4, 'D': 5, 'D#': 6, 'Eb': 6, 'E': 7, 'F': 8, 'F#': 9, 'Gb': 9, 'G': 10, 'G#': 11, 'Ab': 11}
    
    fret_s6 = ROOT_FRETS_S6.get(root)
    fret_s5 = ROOT_FRETS_S5.get(root)
    
    voicing = [None] * 6
    
    if fret_s6 is not None and (fret_s6 <= 5 or fret_s5 is None or fret_s5 > 5):
        r = fret_s6
        shape = SHAPES_S6.get(q_type, SHAPES_S6["major"])
        for string_idx, offset in shape.items():
            voicing[string_idx] = r + offset
    elif fret_s5 is not None:
        r = fret_s5
        shape = SHAPES_S5.get(q_type, SHAPES_S5["major"])
        for string_idx, offset in shape.items():
            voicing[string_idx] = r + offset
            
    for f in voicing:
        if f is not None and (f < 0 or f > 18):
            raise ValueError(f"Voicing out of bounds for {name}")
            
    return voicing

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
    ax.set_aspect('equal')
    ax.axis('off')
    
    if title:
        plt.title(title, color='#f7f7ff', fontsize=12, fontweight='bold', pad=10)
        
    plt.tight_layout()
    return fig

def draw_guitar_chord(voicing, chord_name=""):
    fig, ax = plt.subplots(figsize=(4, 5.5), facecolor='#1e1e24')
    ax.set_facecolor('#1e1e24')
    
    # Filter out None and 0 to find active frets
    fingered_frets = [f for f in voicing if f is not None and f > 0]
    if fingered_frets:
        min_fret = min(fingered_frets)
        max_fret = max(fingered_frets)
        if max_fret <= 4:
            start_fret = 1
            is_nut = True
        else:
            start_fret = min_fret
            is_nut = False
    else:
        start_fret = 1
        is_nut = True
        
    # 6 strings vertical lines
    for string_idx in range(6):
        linewidth = 1.0 + (5 - string_idx) * 0.4 # Low strings are thicker
        ax.plot([string_idx, string_idx], [0, 4], color='#8d99ae', linewidth=linewidth, zorder=1)
        
    # 5 frets horizontal lines
    for fret_idx in range(5):
        if fret_idx == 0:
            if is_nut:
                # The nut (thicker top line)
                ax.plot([-0.1, 5.1], [4, 4], color='#f7f7ff', linewidth=4.0, zorder=2)
            else:
                # Normal thin top line
                ax.plot([0, 5], [4, 4], color='#8d99ae', linewidth=1.5, zorder=1)
        else:
            ax.plot([0, 5], [4 - fret_idx, 4 - fret_idx], color='#8d99ae', linewidth=1.5, zorder=1)
            
    # Draw contiguous barre lines
    from collections import defaultdict
    fret_strings = defaultdict(list)
    for idx, val in enumerate(voicing):
        if val is not None and val > 0:
            fret_strings[val].append(idx)
            
    for fret, strings in fret_strings.items():
        if len(strings) >= 3:
            strings.sort()
            groups = []
            cur_group = [strings[0]]
            for s in strings[1:]:
                if s == cur_group[-1] + 1:
                    cur_group.append(s)
                else:
                    groups.append(cur_group)
                    cur_group = [s]
            groups.append(cur_group)
            
            for g in groups:
                if len(g) >= 3:
                    fret_relative = fret - start_fret + 1
                    barre_y = 4.5 - fret_relative
                    ax.plot([g[0], g[-1]], [barre_y, barre_y], color='#06d6a0', linewidth=16, solid_capstyle='round', zorder=3)
            
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
            fret_relative = fret - start_fret + 1
            fret_y = 4.5 - fret_relative
            circle = patches.Circle((string_x, fret_y), 0.28, color='#06d6a0', zorder=4)
            ax.add_patch(circle)
            # Add note label
            ax.text(string_x, fret_y, string_labels[idx], color='#1e1e24', fontsize=9, fontweight='bold', ha='center', va='center', zorder=5)
            
    # Add fret numbers on the left
    for fret_idx in range(1, 5):
        actual_fret = start_fret + fret_idx - 1
        ax.text(-0.6, 4.5 - fret_idx, f"fr {actual_fret}", color='#8d99ae', fontsize=9, ha='center', va='center')
        
    ax.set_xlim(-0.8, 5.8)
    ax.set_ylim(-0.5, 4.8)
    ax.set_aspect('equal')
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
            name = args.chord_name.strip()
            if not name:
                raise ValueError("Chord name is required for guitar fretboard lookup.")
                
            try:
                voicing = get_guitar_voicing(name)
                chord_title = name
            except Exception as e:
                # Default to C Major if parsing/voicing fails
                voicing = OPEN_CHORDS["C Major"]
                chord_title = f"{name} (Default C)"
                print(f"Voicing resolution failed for {name}: {e}")
                
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
