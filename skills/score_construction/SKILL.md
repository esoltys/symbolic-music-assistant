---
name: building-symbolic-scores
description: Manages step-by-step state manipulation of a localized structural JSON file tracking active note/rest token streams, and validates voice-leading.
permission_tier: Draft-Only
allowed-tools:
  - score_manager
  - check_voice_leading
  - assign_instrument_to_track
  - set_score_tempo
---

# building-symbolic-scores

## Focus & Capabilities
This skill manages the sequential creation, mutation, and validation of a symbolic musical score. It represents notes, durations, and rests inside a localized JSON structural file representing the score state.
- Initializing a blank score with specific time and key signatures.
- Appending note tokens (pitch and duration) to the active score stream.
- Modifying or clearing elements of the score.
- Validating the score for voice-leading errors (parallel fifths/octaves) and vocal range violations.

## Triggers
This skill is triggered when the user requests to build, modify, add notes, or validate a score, including:
- "Initialize a blank 4/4 score."
- "Add a quarter note C4 to the score."
- "Write a scale/melody to the score."
- "Write a melody using ABC notation."
- "Add tinyNotation: C4 D E F."
- "Check the active score for voice-leading errors."
- "Validate my composition."
- "Are there any parallel fifths or octaves in the score?"

## Non-Capabilities
- This skill does NOT perform general music theory calculations (handled by `querying-music-theory` when unrelated to score validation).
- This skill does NOT play or synthesize audio files.
- This skill does NOT read raw MIDI input files directly.

