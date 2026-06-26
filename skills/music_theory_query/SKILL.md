---
name: querying-music-theory
description: Focused exclusively on interval calculations, mode parsing, basic step math, and key signature detection.
permission_tier: Read-Only
allowed-tools:
  - detect_key
---

# querying-music-theory

## Focus & Capabilities
This skill handles symbolic music theory inquiries, including:
- Calculating semitone distances between pitches (e.g., C4 to G4).
- Parsing musical modes (e.g., Dorian, Phrygian) and scales.
- Step-wise scale degrees and interval arithmetic.
- Analyzing active scores or MIDI files to detect/estimate the musical key.

## Triggers
This skill is triggered when the user queries about:
- Distances or intervals between specific pitches (e.g., "What is the interval between C4 and G4?").
- Musical modes or scale degrees (e.g., "What are the notes of D Dorian?").
- Semitone step math.
- Detecting or identifying the key of a score or MIDI file (e.g., "What key is this MIDI in?", "Analyze the key of the current score").

## Non-Capabilities (What this is NOT for)
- This skill does NOT play or synthesize audio files.
- This skill does NOT handle MIDI file import or export.
- This skill does NOT modify local source code or workspace files.

