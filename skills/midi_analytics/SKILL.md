---
name: analyzing-midi-files
description: Ingests raw binary MIDI assets via chat attachments, extracting lightweight structural summary metrics (track count, tempo, note count) without writing to disk permanently.
permission_tier: Read-Only
allowed-tools:
  - parse_midi_metrics
---

# analyzing-midi-files

## Focus & Capabilities
This skill analyzes binary MIDI files attached directly to the chat or uploaded by the user. It extracts structural parameters from the MIDI file without modifying any files on disk permanently:
- Extracting track count.
- Computing tempo / BPM metrics.
- Counting total notes.

## Triggers
This skill is triggered when the user queries for MIDI analysis, statistics, or metrics from a file, including:
- "Analyze the attached MIDI file."
- "How many tracks are in the MIDI file I uploaded?"
- "What is the tempo of the attached midi?"

## Non-Capabilities
- This skill does NOT play or synthesize audio files.
- This skill does NOT edit, save, or output new MIDI files (which belongs to a different mutation skill).
- This skill does NOT perform scale or mode queries (handled by `querying-music-theory`).
