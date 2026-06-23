---
name: analyzing-midi-files
description: Ingests raw binary MIDI assets via local paths, extracting lightweight structural summary metrics (track count, tempo, note count) without writing to disk.
permission_tier: Read-Only
allowed-tools:
  - parse_midi_metrics
---

# analyzing-midi-files

## Focus & Capabilities
This skill analyzes binary MIDI files located at a given local filepath. It extracts structural parameters from the MIDI file without modifying any files on disk:
- Extracting track count.
- Computing tempo / BPM metrics.
- Counting total notes.

## Triggers
This skill is triggered when the user queries for MIDI analysis, statistics, or metrics from a file, including:
- "Analyze this MIDI file: path/to/file.mid"
- "How many tracks are in the MIDI file at path/to/file.mid?"
- "What is the tempo of the midi at path/to/file.mid?"

## Non-Capabilities
- This skill does NOT play or synthesize audio files.
- This skill does NOT edit, save, or output new MIDI files (which belongs to a different mutation skill).
- This skill does NOT perform scale or mode queries (handled by `querying-music-theory`).
