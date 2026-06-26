# Symbolic Music Assistant

A powerful, AI-driven symbolic music assistant built using the [Agent Development Kit (ADK)](https://adk.dev/), `music21`, `pretty_midi`, and `FluidSynth`. 

This assistant is designed to help musicians, composers, and developers analyze music, construct scores, perform music theory calculations, render visual notation, and synthesize audio.

---

## 🎵 What Can the Assistant Do? (User Guide)

The assistant is equipped with specialized **Skills** to assist you with various music tasks. Below is a summary of its capabilities and examples of questions or prompts you can ask:

### 1. Score Construction & Melodic Composition (`building-symbolic-scores`)
Build, edit, and convert musical scores. The assistant keeps track of your active session's score state (keys, time signatures, notes, rests, and chords).
* **Capabilities**:
  * Initialize new scores with specific time and key signatures.
  * Append single notes, chords, or rests (specifying pitch, duration, and track/part).
  * Build complex multi-part scores (e.g., melody, bassline).
  * Transpose the active score up or down by any number of semitones.
  * Export the active score to standard MIDI (`.mid`) files as session artifacts.
  * Import external MIDI files directly into the active score state for rendering or synthesis.
  * Validate the active score for voice-leading violations (parallel fifths/octaves) and vocal range errors.
* **Example Questions & Prompts**:
  * *"Initialize a blank 4/4 score in G Major."*
  * *"Add a quarter note C4 to the melody."*
  * *"Transpose the active score up 2 semitones."*
  * *"Export the score to a MIDI file."*
  * *"Import the MIDI file at skills/midi_analytics/assets/sample.mid"*
  * *"Check the active score for voice-leading errors."*

### 2. Music Theory Queries (`querying-music-theory`)
Perform quick and accurate symbolic music theory calculations.
* **Capabilities**:
  * Calculate interval distances and interval names between pitches.
  * Spell scales and modes (e.g., Major, Minor, Dorian, Phrygian, Lydian, Mixolydian, Locrian).
  * Identify chords, inversions, and triad status from notes.
  * Perform Roman numeral analysis of chords in a given key signature.
  * Detect/estimate the key signature of the active score or an external MIDI file.
* **Example Questions & Prompts**:
  * *"What is the interval between C4 and G#4?"*
  * *"What are the notes in D Dorian?"*
  * *"What chord is C4, E-4, G4, B-4?"*
  * *"What is the Roman numeral of C4, E4, G4 in G Major?"*
  * *"What key is this MIDI file in?"*

### 3. MIDI File Analytics (`analyzing-midi-files`)
Ingest and analyze existing MIDI files to extract structural metrics.
* **Capabilities**:
  * Count tracks, total note events, and list detailed track/instrument programs and names.
  * Extract global tempo (BPM) and time signatures.
* **Example Questions & Prompts**:
  * *"Analyze this MIDI file: path/to/song.mid"*
  * *"What is the tempo of the midi at path/to/track.mid?"*
  * *"How many notes and tracks are in the MIDI file at path/to/composition.mid?"*
  * *"What instruments are in the MIDI file at path/to/song.mid?"*

### 4. Visual Notation Rendering (`rendering-visual-notation`)
Generate visual representations of your active score.
* **Capabilities**:
  * Render piano rolls and timeline notation graphs using `matplotlib`.
  * Export high-fidelity MusicXML files ready for inspection in external score editors like MuseScore.
* **Example Questions & Prompts**:
  * *"Show a visualization of the current score."*
  * *"Render the active score to an image."*
  * *"Graph the current notes."*

### 5. Acoustic Audio Synthesis (`synthesizing-acoustic-audio`)
Hear your creations by compiling note sequences into audio.
* **Capabilities**:
  * Synthesize note events from your active score into concrete WAV files on disk.
  * Uses FluidSynth with high-quality acoustic grand piano sound fonts.
* **Example Questions & Prompts**:
  * *"Synthesize the current score to audio."*
  * *"Convert the active score notes into a piano wav file."*
  * *"Render the score as audio."*

---

## 🛠️ Developer Guide

### Project Structure

```
symbolic-music-assistant/
├── app/         # Core agent code (weather/time stubs)
│   ├── agent.py               # Main agent logic
│   └── app_utils/             # App utilities and helpers
├── agents/      # ADK CLI agent logic
│   ├── agent.py               # Wrapper to expose agent
│   └── music_assistant/       # Core music assistant agent and tools
├── skills/      # Custom music skills (theory, score, midi, render, synth)
├── tests/                     # Unit, integration, and load tests
├── GEMINI.md                  # AI-assisted development guide
└── pyproject.toml             # Project dependencies
```

> 💡 **Tip:** Use [Google Antigravity](https://antigravity.google/) for AI-assisted development - project context is pre-configured in [GEMINI.md](GEMINI.md).

### Requirements

Before you begin, ensure you have:
- **uv**: Python package manager (used for all dependency management in this project) - [Install](https://docs.astral.sh/uv/getting-started/installation/) ([add packages](https://docs.astral.sh/uv/concepts/dependencies/) with `uv add <package>`)
- **agents-cli**: Agents CLI - Install with `uv tool install google-agents-cli`
- **Google Cloud SDK**: For GCP services - [Install](https://cloud.google.com/sdk/docs/install)

### Quick Start

Install `agents-cli` and its skills if not already installed:

```bash
uvx google-agents-cli setup
agents-cli install
agents-cli playground
```

You can also use features from the [ADK](https://adk.dev/) CLI with `uv run adk`.

### Commands

| Command              | Description                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------- |
| `agents-cli install` | Install dependencies using uv                                                         |
| `agents-cli playground` | Launch local development environment                                                  |
| `agents-cli lint`    | Run code quality checks                                                               |
| `agents-cli eval`    | Evaluate agent behavior (generate, grade, analyze, and more — see `agents-cli eval --help`) |
| `uv run pytest tests/unit tests/integration` | Run unit and integration tests                                                        |

### 🛠️ Project Management

| Command | What It Does |
|---------|--------------|
| `agents-cli scaffold enhance` | Add CI/CD pipelines and Terraform infrastructure |
| `agents-cli infra cicd` | One-command setup of entire CI/CD pipeline + infrastructure |
| `agents-cli scaffold upgrade` | Auto-upgrade to latest version while preserving customizations |

### Development

Edit your agent logic in `agents/music_assistant/agent.py` and test with `agents-cli playground` - it auto-reloads on save.

### Deployment

```bash
gcloud config set project <your-project-id>
agents-cli deploy
```

To add CI/CD and Terraform, run `agents-cli scaffold enhance`.
To set up your production infrastructure, run `agents-cli infra cicd`.

### Observability

Built-in telemetry exports to Cloud Trace, BigQuery, and Cloud Logging.
