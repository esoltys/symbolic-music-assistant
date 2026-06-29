"""MCP server for Cadence — Music Assistant Tools.

Exposes the full suite of music theory, score construction, MIDI analytics,
notation rendering, and audio synthesis tools as a Model Context Protocol (MCP)
server so that external MCP clients (e.g. Claude Desktop, other ADK agents, or
any MCP-compatible application) can call them directly.
"""

import os
import sys
import subprocess
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Import stateless helpers from the main agent to avoid duplicating static definitions
try:
    from agents.music_assistant.agent import list_soundfonts as _list_soundfonts
    from agents.music_assistant.agent import list_soundfont_instruments as _list_instruments
except ImportError:
    # Fallback to local stub implementations if importing fails
    def _list_soundfonts():
        return json.dumps({"status": "success", "soundfonts": []})
    def _list_instruments():
        return json.dumps({"status": "success", "instrument_categories": {}})

# ---------------------------------------------------------------------------
# Security helpers (mirrors agents/music_assistant/agent.py)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent.resolve()
_MAX_ARG_LEN = 256





def _safe_decode_base64(b64_str: str) -> bytes:
    """Safely decode base64 file content, handling data URL prefixes, stripping invalid formatting, and fixing padding."""
    import base64
    # Clean up whitespace and quotes
    b64_str = b64_str.strip().strip("'\"")
    # Strip data URL prefix if present (e.g. data:audio/midi;base64,TVRoZ...)
    if "," in b64_str and ";base64" in b64_str.split(",")[0]:
        b64_str = b64_str.split(",")[1]
    # Ensure proper padding
    missing_padding = len(b64_str) % 4
    if missing_padding:
        b64_str += '=' * (4 - missing_padding)
    return base64.b64decode(b64_str)


def _sanitize_arg(value: str, max_len: int = _MAX_ARG_LEN) -> str:
    """Truncate a string argument to a safe maximum length."""
    return value[:max_len]


# ---------------------------------------------------------------------------
# FastMCP server definition
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="cadence-music-theory",
    instructions=(
        "A music theory and score construction MCP server for Cadence, the AI music assistant. "
        "Provides stateless music theory queries, alongside score construction, voice leading checks, "
        "notation rendering, and audio synthesis (WAV files using SoundFonts)."
    ),
)


def _run_script(script_path: Path, args: list[str]) -> str:
    """Execute a skills script as a subprocess and return its JSON output.

    Args:
        script_path: Absolute path to the Python script to run.
        args: List of string arguments to pass after the script path.

    Returns:
        The stdout JSON string from the script, or a JSON error object.
    """
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), *args],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        return result.stdout or result.stderr or json.dumps(
            {"status": "error", "error": "No output from script."}
        )
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


# ===========================================================================
# 1. Stateless Music Theory Tools
# ===========================================================================

@mcp.tool()
def evaluate_interval(start_note: str, end_note: str) -> str:
    """Calculate the semitone distance and canonical interval name between two pitches.

    Args:
        start_note: Starting note with octave (e.g. 'C4', 'E-3', 'F#5').
        end_note:   Ending note with octave   (e.g. 'G4', 'D6', 'B#2').

    Returns:
        JSON with keys: status, start_note, end_note, semitones, interval_name.
    """
    start_note = _sanitize_arg(start_note)
    end_note = _sanitize_arg(end_note)
    script = _PROJECT_ROOT / "skills" / "music_theory_query" / "scripts" / "evaluate_intervals.py"
    return _run_script(script, [start_note, end_note])


@mcp.tool()
def list_scale_pitches(tonic: str, scale_type: str) -> str:
    """Generate the notes of a scale or mode.

    Args:
        tonic:      Tonic note name (e.g. 'C', 'F#', 'B-').
        scale_type: Scale/mode type: 'major', 'minor', 'dorian', 'phrygian',
                    'lydian', 'mixolydian', or 'locrian'.

    Returns:
        JSON with keys: status, tonic, scale_type, pitches (list of note names).
    """
    tonic = _sanitize_arg(tonic)
    scale_type = _sanitize_arg(scale_type)
    script = _PROJECT_ROOT / "skills" / "music_theory_query" / "scripts" / "list_scale_pitches.py"
    return _run_script(script, [tonic, scale_type])


@mcp.tool()
def analyze_chord(pitches: str, key_signature: str = "") -> str:
    """Identify a chord and optionally compute its Roman numeral in a given key.

    Args:
        pitches:       Comma-separated pitch names (e.g. 'C4,E4,G4').
        key_signature: Optional key for Roman numeral analysis (e.g. 'G Major').
                       Omit or pass an empty string to skip Roman numeral analysis.

    Returns:
        JSON with keys: status, pitches, common_name, full_name, inversion,
        is_triad, and optionally roman_numeral and key.
    """
    pitches = _sanitize_arg(pitches)
    key_signature = _sanitize_arg(key_signature)
    script = _PROJECT_ROOT / "skills" / "music_theory_query" / "scripts" / "analyze_chord.py"
    args = [pitches]
    if key_signature:
        args += ["--key", key_signature]
    return _run_script(script, args)


@mcp.tool()
def detect_key(file_attachment: dict = None, session_id: str = "default") -> str:
    """Estimate/detect the musical key signature of the active score or a MIDI file attachment.

    Args:
        file_attachment: Optional structured object containing {"fileName": "string", "mimeType": "string", "base64Data": "string"}.
        session_id:      The unique score session ID. Defaults to 'default'.

    Returns:
        JSON with keys: status, detected_key, confidence, relative_keys.
    """
    session_id = _sanitize_arg(session_id)
    resolved_path = ""
    
    if file_attachment:
        if not isinstance(file_attachment, dict):
            return json.dumps({"status": "error", "error": "Invalid file_attachment argument."})
        b64_str = file_attachment.get("base64Data") or file_attachment.get("base64_data")
        if not b64_str:
            return json.dumps({"status": "error", "error": "Missing base64Data inside file_attachment."})
            
        try:
            content = _safe_decode_base64(b64_str)
            if not content.startswith(b"MThd"):
                return json.dumps({"status": "error", "error": "Invalid MIDI file: decoded content does not start with MThd header."})
            
            temp_dir = _PROJECT_ROOT / "skills" / "music_theory_query" / "assets"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_file = temp_dir / f"temp_{session_id}.mid"
            temp_file.write_bytes(content)
            resolved_path = str(temp_file.resolve())
        except Exception as e:
            return json.dumps({"status": "error", "error": f"Failed to decode base64 MIDI content: {e}"})

    script = _PROJECT_ROOT / "skills" / "music_theory_query" / "scripts" / "detect_key.py"
    args = []
    if resolved_path:
        args += ["--midi-path", resolved_path]
    else:
        args += ["--session-id", session_id]
    return _run_script(script, args)


# ===========================================================================
# 2. Score Construction & Editing Tools
# ===========================================================================

@mcp.tool()
def initialize_score(time_signature: str = "4/4", key_signature: str = "C Major", session_id: str = "default") -> str:
    """Initialize a fresh score session.

    Args:
        time_signature: Time signature for the score (default: '4/4').
        key_signature:  Key signature for the score (default: 'C Major').
        session_id:     The unique score session ID. Defaults to 'default'.

    Returns:
        JSON with keys: status, time_signature, key_signature, parts_count.
    """
    time_signature = _sanitize_arg(time_signature)
    key_signature = _sanitize_arg(key_signature)
    session_id = _sanitize_arg(session_id)
    script = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    return _run_script(script, ["init", "--time-signature", time_signature, "--key-signature", key_signature, "--session-id", session_id])


@mcp.tool()
def add_note_to_score(pitch: str, duration: str, part_id: str = "melody", session_id: str = "default") -> str:
    """Add/append a note, chord, or rest token to the score for a specific part.

    Args:
        pitch:      Pitch name (e.g. 'C4', 'rest', or a comma-separated chord like 'C4,E4,G4').
        duration:   Duration of the token (e.g. 'quarter', 'half', 'eighth', 'whole').
        part_id:    ID of the part/track (e.g. 'melody', 'bassline'). Defaults to 'melody'.
        session_id: The unique score session ID. Defaults to 'default'.

    Returns:
        JSON with keys: status, added_event, measure_number.
    """
    pitch = _sanitize_arg(pitch)
    duration = _sanitize_arg(duration)
    part_id = _sanitize_arg(part_id)
    session_id = _sanitize_arg(session_id)
    script = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    return _run_script(script, ["add", "--pitch", pitch, "--duration", duration, "--part-id", part_id, "--session-id", session_id])


@mcp.tool()
def transpose_score(semitones: int, session_id: str = "default") -> str:
    """Transpose all notes/chords and key signatures in the active score up or down by a given number of semitones.

    Args:
        semitones:  Number of semitones to transpose (e.g. 2 for up a whole step, -3 for down a minor third).
        session_id: The unique score session ID. Defaults to 'default'.

    Returns:
        JSON with keys: status, transposition, new_key_signature.
    """
    session_id = _sanitize_arg(session_id)
    script = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    return _run_script(script, ["transpose", "--semitones", str(semitones), "--session-id", session_id])


@mcp.tool()
def set_score_tempo(bpm: float, offset: float = 0.0, session_id: str = "default") -> str:
    """Set or change the tempo (in BPM) at a specific beat offset in the active score.

    Args:
        bpm:        The tempo in beats per minute (BPM).
        offset:     The beat offset at which this tempo applies (default 0.0 for start of score).
        session_id: The unique score session ID. Defaults to 'default'.

    Returns:
        JSON with keys: status, tempo, offset.
    """
    session_id = _sanitize_arg(session_id)
    script = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    return _run_script(script, ["set-tempo", "--bpm", str(bpm), "--offset", str(offset), "--session-id", session_id])


@mcp.tool()
def validate_voice_leading(session_id: str = "default") -> str:
    """Check the active score for voice-leading violations (parallel fifths/octaves) and range errors.

    Args:
        session_id: The unique score session ID. Defaults to 'default'.

    Returns:
        JSON with keys: status, violation_status, parallels, range_errors.
    """
    session_id = _sanitize_arg(session_id)
    script = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "check_voice_leading.py"
    return _run_script(script, ["--session-id", session_id])


# ===========================================================================
# 3. Import / Export & MIDI Analytics Tools
# ===========================================================================

@mcp.tool()
def export_score_to_midi(session_id: str = "default") -> str:
    """Export the active score session to a standard MIDI (.mid) file.

    Args:
        session_id: The unique score session ID. Defaults to 'default'.

    Returns:
        JSON with keys: status, midi_path.
    """
    session_id = _sanitize_arg(session_id)
    script = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    res_json = _run_script(script, ["export-midi", "--session-id", session_id])
    try:
        data = json.loads(res_json)
        if data.get("status") == "success" and "midi_path" in data:
            assets_dir = _PROJECT_ROOT / "skills" / "score_construction" / "assets"
            midi_file = assets_dir / f"score_{session_id}.mid"
            data["midi_path"] = str(midi_file.resolve())
            data["resource_uri"] = f"music://scores/{session_id}/score.mid"
            return json.dumps(data, indent=2)
    except Exception:
        pass
    return res_json


@mcp.tool()
def import_midi_to_score(file_attachment: dict, session_id: str = "default") -> str:
    """Import an external MIDI file attachment into the active score session.

    Args:
        file_attachment: A structured object containing {"fileName": "string", "mimeType": "string", "base64Data": "string"}.
        session_id:      The unique score session ID. Defaults to 'default'.

    Returns:
        JSON with keys: status, tracks_imported, key_signature, tempo.
    """
    session_id = _sanitize_arg(session_id)
    if not file_attachment or not isinstance(file_attachment, dict):
        return json.dumps({"status": "error", "error": "Invalid or missing file_attachment argument."})
        
    b64_str = file_attachment.get("base64Data") or file_attachment.get("base64_data")
    if not b64_str:
        return json.dumps({"status": "error", "error": "Missing base64Data inside file_attachment."})
        
    try:
        content = _safe_decode_base64(b64_str)
        if not content.startswith(b"MThd"):
            return json.dumps({"status": "error", "error": "Invalid MIDI file: decoded content does not start with MThd header."})
        
        temp_dir = _PROJECT_ROOT / "skills" / "score_construction" / "assets"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file = temp_dir / f"temp_{session_id}.mid"
        temp_file.write_bytes(content)
        resolved_path = str(temp_file.resolve())
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to decode base64 MIDI content: {e}"})

    script = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    return _run_script(script, ["import-midi", "--midi-path", resolved_path, "--session-id", session_id])


@mcp.tool()
def analyze_midi_file(file_attachment: dict) -> str:
    """Ingest a raw binary MIDI file attachment and extract track count, tempo, note count, and instruments.

    Args:
        file_attachment: A structured object containing {"fileName": "string", "mimeType": "string", "base64Data": "string"}.

    Returns:
        JSON with keys: status, track_count, tempo, note_count, instruments.
    """
    if not file_attachment or not isinstance(file_attachment, dict):
        return json.dumps({"status": "error", "error": "Invalid or missing file_attachment argument."})
        
    b64_str = file_attachment.get("base64Data") or file_attachment.get("base64_data")
    if not b64_str:
        return json.dumps({"status": "error", "error": "Missing base64Data inside file_attachment."})
        
    try:
        content = _safe_decode_base64(b64_str)
        if not content.startswith(b"MThd"):
            return json.dumps({"status": "error", "error": "Invalid MIDI file: decoded content does not start with MThd header."})
        
        temp_dir = _PROJECT_ROOT / "skills" / "midi_analytics" / "assets"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file = temp_dir / "temp_upload.mid"
        temp_file.write_bytes(content)
        resolved_path = str(temp_file.resolve())
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to decode base64 MIDI content: {e}"})

    script = _PROJECT_ROOT / "skills" / "midi_analytics" / "scripts" / "parse_midi_metrics.py"
    return _run_script(script, ["--file-path", resolved_path])


# ===========================================================================
# 4. Audio Synthesis & Instrument Assignment Tools
# ===========================================================================

@mcp.tool()
def list_soundfonts() -> str:
    """List the available SoundFont (.sf2) files and their descriptions.

    Returns:
        JSON string containing the list of soundfonts.
    """
    return _list_soundfonts()


@mcp.tool()
def list_soundfont_instruments() -> str:
    """List the available instrument patches inside the General MIDI soundfont (TimGM6mb.sf2).

    Returns:
        JSON string containing categories and program numbers.
    """
    return _list_instruments()


@mcp.tool()
def assign_instrument_to_track(part_id: str, program: int, is_percussion: bool = False, session_id: str = "default") -> str:
    """Manually assign a specific General MIDI instrument (0-127) to a track/part in the score.

    Args:
        part_id:       The ID of the part/track (e.g. 'melody', 'part_1').
        program:       The MIDI program number (0-127) for the instrument.
        is_percussion: Set to True if this track is unpitched drums/percussion.
        session_id:    The unique score session ID. Defaults to 'default'.

    Returns:
        JSON with keys: status, part_id, program, is_percussion.
    """
    part_id = _sanitize_arg(part_id)
    session_id = _sanitize_arg(session_id)
    script = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    args = ["assign-instrument", "--part-id", part_id, "--program", str(program), "--session-id", session_id]
    if is_percussion:
        args.append("--percussion")
    return _run_script(script, args)


@mcp.tool()
def synthesize_score(tracks: str = "", soundfont: str = "", session_id: str = "default") -> str:
    """Compile the notes from the score session into a WAV audio file using a SoundFont.

    Args:
        tracks:     Optional comma-separated list of track IDs or names to play.
        soundfont:  Optional soundfont filename (e.g. 'TimGM6mb.sf2' or 'SalamanderGrandPiano-V3+20200602.sf2').
        session_id: The unique score session ID. Defaults to 'default'.

    Returns:
        JSON with keys: status, audio_path, soundfont.
    """
    tracks = _sanitize_arg(tracks)
    soundfont = _sanitize_arg(soundfont)
    session_id = _sanitize_arg(session_id)
    script = _PROJECT_ROOT / "skills" / "acoustic_audio_synthesis" / "scripts" / "synthesize_score.py"
    args = ["--session-id", session_id]
    if tracks:
        args += ["--tracks", tracks]
    if soundfont:
        args += ["--soundfont", soundfont]

    res_json = _run_script(script, args)
    try:
        data = json.loads(res_json)
        if data.get("status") == "success" and "audio_path" in data:
            assets_dir = _PROJECT_ROOT / "skills" / "acoustic_audio_synthesis" / "assets"
            wav_file = assets_dir / f"score_{session_id}.wav"
            data["audio_path"] = str(wav_file.resolve())
            data["resource_uri"] = f"music://scores/{session_id}/score.wav"
            return json.dumps(data, indent=2)
    except Exception:
        pass
    return res_json


# ===========================================================================
# 5. Visual Notation Rendering Tools
# ===========================================================================

@mcp.tool()
def render_notation(tracks: str = "", session_id: str = "default") -> str:
    """Render the current score state to visual piano roll and notation timeline graphs.

    Args:
        tracks:     Optional comma-separated list of track IDs or names to render.
        session_id: The unique score session ID. Defaults to 'default'.

    Returns:
        JSON with keys: status, piano_roll, score_plot, notation_layout, musicxml_path.
    """
    tracks = _sanitize_arg(tracks)
    session_id = _sanitize_arg(session_id)
    script = _PROJECT_ROOT / "skills" / "visual_notation_rendering" / "scripts" / "generate_visuals.py"
    args = ["--session-id", session_id]
    if tracks:
        args += ["--tracks", tracks]

    res_json = _run_script(script, args)
    try:
        data = json.loads(res_json)
        if data.get("status") == "success":
            assets_dir = _PROJECT_ROOT / "skills" / "visual_notation_rendering" / "assets"
            for key in ["piano_roll", "score_plot", "notation_layout", "musicxml_path"]:
                if key in data and data[key]:
                    filename = Path(data[key]).name
                    data[key] = str((assets_dir / filename).resolve())
            data["piano_roll_uri"] = f"music://scores/{session_id}/piano_roll.png"
            data["score_plot_uri"] = f"music://scores/{session_id}/score_plot.png"
            data["musicxml_uri"] = f"music://scores/{session_id}/score.musicxml"
            return json.dumps(data, indent=2)
    except Exception:
        pass
    return res_json


# ===========================================================================
# 6. MCP Resources (Exposing Files to the Client)
# ===========================================================================

@mcp.resource("music://scores/{session_id}/score.mid", mime_type="audio/midi")
def get_score_midi(session_id: str) -> bytes:
    """Get the exported MIDI file bytes for a session."""
    session_id = _sanitize_arg(session_id)
    midi_file = _PROJECT_ROOT / "skills" / "score_construction" / "assets" / f"score_{session_id}.mid"
    if midi_file.is_file():
        return midi_file.read_bytes()
    raise FileNotFoundError(f"MIDI file not found for session: {session_id}")


@mcp.resource("music://scores/{session_id}/score.musicxml", mime_type="application/xml")
def get_score_xml(session_id: str) -> str:
    """Get the MusicXML score content for a session."""
    session_id = _sanitize_arg(session_id)
    xml_file = _PROJECT_ROOT / "skills" / "visual_notation_rendering" / "assets" / f"score_{session_id}.musicxml"
    if xml_file.is_file():
        return xml_file.read_text(encoding="utf-8")
    raise FileNotFoundError(f"MusicXML file not found for session: {session_id}")


@mcp.resource("music://scores/{session_id}/piano_roll.png", mime_type="image/png")
def get_piano_roll(session_id: str) -> bytes:
    """Get the rendered piano roll image bytes for a session."""
    session_id = _sanitize_arg(session_id)
    img_file = _PROJECT_ROOT / "skills" / "visual_notation_rendering" / "assets" / f"piano_roll_{session_id}.png"
    if img_file.is_file():
        return img_file.read_bytes()
    raise FileNotFoundError(f"Piano roll image not found for session: {session_id}")


@mcp.resource("music://scores/{session_id}/score_plot.png", mime_type="image/png")
def get_score_plot(session_id: str) -> bytes:
    """Get the rendered score plot image bytes for a session."""
    session_id = _sanitize_arg(session_id)
    img_file = _PROJECT_ROOT / "skills" / "visual_notation_rendering" / "assets" / f"score_plot_{session_id}.png"
    if img_file.is_file():
        return img_file.read_bytes()
    raise FileNotFoundError(f"Score plot image not found for session: {session_id}")


@mcp.resource("music://scores/{session_id}/score.wav", mime_type="audio/wav")
def get_score_wav(session_id: str) -> bytes:
    """Get the synthesized WAV audio file bytes for a session."""
    session_id = _sanitize_arg(session_id)
    wav_file = _PROJECT_ROOT / "skills" / "acoustic_audio_synthesis" / "assets" / f"score_{session_id}.wav"
    if wav_file.is_file():
        return wav_file.read_bytes()
    raise FileNotFoundError(f"WAV audio file not found for session: {session_id}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
