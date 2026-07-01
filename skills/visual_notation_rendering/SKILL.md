---
name: rendering-visual-notation
description: Converts active score JSON state file coordinates into inline graphs or static plot files using matplotlib configurations.
permission_tier: Read-Only
allowed-tools:
  - render_notation
  - render_chord_diagram
---

# rendering-visual-notation

## Focus & Capabilities
This skill handles rendering symbolic music notation states into visual representations:
- Reading the active localized score state file coordinates from JSON.
- Generating static plot files or inline graphics (e.g., piano roll or note plots) using `matplotlib` configurations.
- Confirming target image paths.

## Triggers
- "Render the active score to an image."
- "Show a visualization of the score."
- "Graph the current notes."

## Non-Capabilities
- This skill does not modify the score state file.
- This skill does not synthesize audio or MIDI playback.
