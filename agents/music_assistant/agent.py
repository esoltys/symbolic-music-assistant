import os
import sys
import subprocess
import json
from pathlib import Path
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types
from google.adk.tools import ToolContext

# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# Maximum character length for short string arguments passed to subprocesses
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
    """Truncate a string argument to a safe maximum length before passing to a subprocess.

    Note: inputs are passed as argv items (no shell=True), so shell injection is
    not a direct risk, but capping length guards against denial-of-service via
    oversized inputs and keeps error messages intelligible.

    Args:
        value: The string value to sanitize.
        max_len: Maximum allowed character length (default 256).

    Returns:
        The original string if within bounds, otherwise truncated to max_len.
    """
    return value[:max_len]

def evaluate_interval(start_note: str, end_note: str) -> str:
    """Calculates the semitone distance and canonical interval name between two note pitches.

    Args:
        start_note: The starting note name (e.g., 'C4', 'E-3', 'F#5').
        end_note: The ending note name (e.g., 'G4', 'D6', 'B#2').

    Returns:
        A JSON string containing the status, calculated semitones, interval name, or error details.
    """
    script_path = _PROJECT_ROOT / "skills" / "music_theory_query" / "scripts" / "evaluate_intervals.py"
    start_note = _sanitize_arg(start_note)
    end_note = _sanitize_arg(end_note)

    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), start_note, end_note],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from execution script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute interval calculation script: {e}"})

def list_scale_pitches(tonic: str, scale_type: str) -> str:
    """Generates the notes/pitches of a specific scale or mode.

    Args:
        tonic: The tonic note name (e.g., 'C', 'F#', 'B-').
        scale_type: The scale/mode type (e.g., 'major', 'minor', 'dorian', 'phrygian', 'lydian', 'mixolydian', 'locrian').

    Returns:
        A JSON string containing the status, tonic, scale type, and list of pitches.
    """
    script_path = _PROJECT_ROOT / "skills" / "music_theory_query" / "scripts" / "list_scale_pitches.py"
    tonic = _sanitize_arg(tonic)
    scale_type = _sanitize_arg(scale_type)

    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), tonic, scale_type],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from scale spelling script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute scale spelling script: {e}"})

def analyze_chord(pitches: str, key_signature: str = "") -> str:
    """Analyzes a chord's notes to determine its name, inversion, triad status, and Roman numeral.

    Args:
        pitches: Comma-separated pitch names (e.g., 'C4,E-4,G4').
        key_signature: Optional key signature for Roman numeral analysis (e.g., 'C Major').

    Returns:
        A JSON string containing the status, pitches, chord name, inversion, triad status, and Roman numeral.
    """
    script_path = _PROJECT_ROOT / "skills" / "music_theory_query" / "scripts" / "analyze_chord.py"
    pitches = _sanitize_arg(pitches)
    key_signature = _sanitize_arg(key_signature)

    python_exe = sys.executable or "python"
    cmd = [python_exe, str(script_path), pitches]
    if key_signature:
        cmd.extend(["--key", key_signature])
        
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from chord analysis script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute chord analysis script: {e}"})


async def render_chord_diagram(tool_context: ToolContext, pitches: str = "", instrument: str = "piano", chord_name: str = "") -> str:
    """Renders a beautiful visual diagram (piano keyboard or guitar fretboard) for a chord.

    Args:
        tool_context: The tool execution context containing session data.
        pitches: The comma-separated note pitches to highlight (e.g. 'C4,E4,G4'). Required if instrument is 'piano'.
        instrument: The visual layout type, either 'piano' or 'guitar' (default: 'piano').
        chord_name: The name of the chord for lookup or title rendering (e.g., 'C Major', 'Am7').

    Returns:
        A JSON string containing the status and relative path of the generated image.
    """
    script_path = _PROJECT_ROOT / "skills" / "visual_notation_rendering" / "scripts" / "draw_chord.py"
    pitches = _sanitize_arg(pitches)
    instrument = _sanitize_arg(instrument)
    chord_name = _sanitize_arg(chord_name)
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    cmd = [
        python_exe, str(script_path),
        "--instrument", instrument,
        "--session-id", session_id
    ]
    if pitches:
        cmd += ["--pitches", pitches]
    if chord_name:
        cmd += ["--chord-name", chord_name]
        
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        
        # Load and save artifact if successful
        if result.returncode == 0:
            try:
                res_dict = json.loads(result.stdout)
            except Exception:
                res_dict = {"status": "success"}
                
            img_path = _PROJECT_ROOT / "skills" / "visual_notation_rendering" / "assets" / f"chord_{session_id}.png"
            if img_path.is_file():
                try:
                    with open(img_path, "rb") as f:
                        data = f.read()
                    await tool_context.save_artifact(
                        filename=f"chord_{session_id}.png",
                        artifact=types.Part.from_bytes(data=data, mime_type="image/png")
                    )
                    res_dict["output_path_absolute"] = str(img_path.resolve().as_posix())
                except Exception as e:
                    print(f"Failed to save chord artifact: {e}")
                    
            return json.dumps(res_dict, indent=2)
            
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from chord diagram generator."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute chord diagram script: {e}"})

def initialize_score(tool_context: ToolContext, time_signature: str = "4/4", key_signature: str = "C Major") -> str:
    """Initializes a fresh localized musical score.

    Args:
        tool_context: The tool execution context containing session data.
        time_signature: The time signature for the score (default: '4/4').
        key_signature: The key signature for the score (default: 'C Major').

    Returns:
        A JSON string containing the status, time_signature, key_signature, and parts_count.
    """
    script_path = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    time_signature = _sanitize_arg(time_signature)
    key_signature = _sanitize_arg(key_signature)
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "init", "--time-signature", time_signature, "--key-signature", key_signature, "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from score manager script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute score manager script: {e}"})

def add_note_to_score(tool_context: ToolContext, pitch: str, duration: str, part_id: str = "melody") -> str:
    """Adds/appends a note, chord, or rest token to the score for a specific part.

    Args:
        tool_context: The tool execution context containing session data.
        pitch: The pitch name (e.g. 'C4', 'rest', or a comma-separated chord like 'C4,E4,G4').
        duration: The duration of the token (e.g. 'quarter', 'half', 'eighth', 'whole').
        part_id: The ID of the part/track (e.g. 'melody', 'bassline'). Defaults to 'melody'.

    Returns:
        A JSON string containing the status, added event details, and measure number.
    """
    script_path = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    pitch = _sanitize_arg(pitch)
    duration = _sanitize_arg(duration)
    part_id = _sanitize_arg(part_id)
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "add", "--pitch", pitch, "--duration", duration, "--part-id", part_id, "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from score manager script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute score manager script: {e}"})

def add_abc_to_score(tool_context: ToolContext, abc: str, part_id: str = "melody") -> str:
    """Adds a sequence of notes, chords, or rests to the active score using ABC notation or TinyNotation.

    Args:
        tool_context: The tool execution context containing session data.
        abc: The ABC notation string (e.g. 'C D E F' or chords '[CEG]') or TinyNotation string (must start with 'tinyNotation:').
        part_id: The ID of the part/track (e.g. 'melody', 'bassline'). Defaults to 'melody'.

    Returns:
        A JSON string containing the status, number of added events, list of added events, and last measure number.
    """
    script_path = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    abc = _sanitize_arg(abc, max_len=4096)
    part_id = _sanitize_arg(part_id)
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "add-abc", "--abc", abc, "--part-id", part_id, "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from score manager script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute score manager script: {e}"})

def transpose_score(tool_context: ToolContext, semitones: int) -> str:
    """Transposes all notes and key signatures in the active score up or down by a number of semitones.

    Args:
        tool_context: The tool execution context containing session data.
        semitones: Number of semitones to transpose (e.g. 2 for up a whole step, -3 for down a minor third).

    Returns:
        A JSON string containing the status, transposition details, and new key signature.
    """
    script_path = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "transpose", "--semitones", str(semitones), "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from score transposition script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute score transposition script: {e}"})


def delete_note_from_score(tool_context: ToolContext, measure: int, event_index: int, part_id: str = "melody", remove_completely: bool = False) -> str:
    """Deletes/removes a note or chord at a specific position in the score.

    Args:
        tool_context: The tool execution context containing session data.
        measure: The 1-indexed measure number of the note to delete.
        event_index: The 0-indexed index of the note/event within the measure.
        part_id: The ID of the part/track (default: 'melody').
        remove_completely: If True, deletes the note event completely (causing subsequent notes to shift left). If False (default), replaces the note with a rest of the same duration.

    Returns:
        A JSON string containing the status and deletion details.
    """
    script_path = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    part_id = _sanitize_arg(part_id)
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    cmd = [
        python_exe, str(script_path), "delete-note",
        "--measure", str(measure),
        "--event-index", str(event_index),
        "--part-id", part_id,
        "--session-id", session_id
    ]
    if remove_completely:
        cmd.append("--remove-completely")
        
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from score manager script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute score manager script: {e}"})


def edit_note_in_score(tool_context: ToolContext, measure: int, event_index: int, part_id: str = "melody", pitch: str = None, duration: str = None) -> str:
    """Edits a note/chord's pitch and/or duration at a specific position in the score.

    Args:
        tool_context: The tool execution context containing session data.
        measure: The 1-indexed measure number of the note to edit.
        event_index: The 0-indexed index of the note/event within the measure.
        part_id: The ID of the part/track (default: 'melody').
        pitch: The new pitch name (e.g. 'E4', 'rest', or a comma-separated chord like 'E4,G4,B4'). Omit or pass None to leave unchanged.
        duration: The new duration name (e.g. 'quarter', 'half', 'eighth'). Omit or pass None to leave unchanged.

    Returns:
        A JSON string containing the status and details of the edit.
    """
    script_path = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    part_id = _sanitize_arg(part_id)
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    cmd = [
        python_exe, str(script_path), "edit-note",
        "--measure", str(measure),
        "--event-index", str(event_index),
        "--part-id", part_id,
        "--session-id", session_id
    ]
    if pitch:
        cmd += ["--pitch", _sanitize_arg(pitch)]
    if duration:
        cmd += ["--duration", _sanitize_arg(duration)]
        
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from score manager script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute score manager script: {e}"})


def insert_measure_into_score(tool_context: ToolContext, at: int) -> str:
    """Inserts a blank measure at a given position across all parts/tracks in the active score.

    Args:
        tool_context: The tool execution context containing session data.
        at: The 1-indexed measure number before which to insert the blank measure.

    Returns:
        A JSON string containing the status and position of insertion.
    """
    script_path = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "insert-measure", "--at", str(at), "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from score manager script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute score manager script: {e}"})


def delete_measure_from_score(tool_context: ToolContext, measure: int) -> str:
    """Deletes a measure at a given position across all parts/tracks in the active score.

    Args:
        tool_context: The tool execution context containing session data.
        measure: The 1-indexed measure number to delete.

    Returns:
        A JSON string containing the status and position of deletion.
    """
    script_path = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "delete-measure", "--measure", str(measure), "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from score manager script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute score manager script: {e}"})


def transpose_part_in_score(tool_context: ToolContext, part_id: str, semitones: int) -> str:
    """Transposes all pitches in a specific part/track of the score by a number of semitones.

    Args:
        tool_context: The tool execution context containing session data.
        part_id: The ID of the part/track to transpose (e.g. 'melody', 'bassline').
        semitones: Number of semitones to transpose (e.g. 2, -3).

    Returns:
        A JSON string containing the status and details of track transposition.
    """
    script_path = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    part_id = _sanitize_arg(part_id)
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "transpose-part", "--part-id", part_id, "--semitones", str(semitones), "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from score manager script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute score manager script: {e}"})

async def export_score_to_midi(tool_context: ToolContext) -> str:
    """Exports the active score session to a standard MIDI (.mid) file and saves it as an artifact.

    Args:
        tool_context: The tool execution context containing session data.

    Returns:
        A JSON string containing the status, midi_path of the generated file, or error details.
    """
    script_path = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "export-midi", "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        
        # Load and save MIDI artifact if successful
        if result.returncode == 0:
            assets_dir = _PROJECT_ROOT / "skills" / "score_construction" / "assets"
            midi_path = assets_dir / f"score_{session_id}.mid"
            if midi_path.is_file():
                with open(midi_path, "rb") as f:
                    data = f.read()
                await tool_context.save_artifact(
                    filename=f"score_{session_id}.mid",
                    artifact=types.Part.from_bytes(data=data, mime_type="audio/midi")
                )
                try:
                    res_dict = json.loads(result.stdout)
                    res_dict["midi_path_absolute"] = str(midi_path.resolve().as_posix())
                    return json.dumps(res_dict, indent=2)
                except Exception:
                    pass
                
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from export-midi script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute export-midi script: {e}"})

async def _extract_attachment_from_context(tool_context: ToolContext) -> dict | None:
    """Helper to extract an attachment from tool_context (current turn, history, or artifacts)
    and return it as a structured file_attachment dictionary.
    """
    if not tool_context:
        return None

    def get_field(obj, field_name, default=None):
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(field_name, default)
        return getattr(obj, field_name, default)

    def extract_from_part(part) -> dict | None:
        if not part:
            return None
        
        # 1. Check inline data
        inline_data = get_field(part, "inline_data")
        if inline_data:
            data = get_field(inline_data, "data")
            mime = get_field(inline_data, "mime_type") or "audio/midi"
            if data:
                if isinstance(data, str):
                    return {"fileName": "attachment.mid", "mimeType": mime, "base64Data": data}
                elif isinstance(data, bytes):
                    import base64
                    b64 = base64.b64encode(data).decode("utf-8")
                    return {"fileName": "attachment.mid", "mimeType": mime, "base64Data": b64}
                    
        # 2. Check uploaded file URIs
        file_data = get_field(part, "file_data")
        if file_data:
            mime = (get_field(file_data, "mime_type") or "").lower()
            file_uri = get_field(file_data, "file_uri")
            midi_mime_types = {"audio/midi", "audio/mid", "audio/x-midi", "audio/sp-midi"}
            if not mime or mime in midi_mime_types or "octet-stream" in mime or "midi" in mime:
                try:
                    from google.genai import Client
                    client = Client()
                    raw_data = client.files.download(file=file_uri)
                    if raw_data:
                        if isinstance(raw_data, bytes):
                            import base64
                            raw_data = base64.b64encode(raw_data).decode("utf-8")
                        filename = Path(file_uri).name if file_uri else "attachment.mid"
                        return {"fileName": filename, "mimeType": mime or "audio/midi", "base64Data": raw_data}
                except Exception as e:
                    print(f"Failed to download attached file from file_uri: {e}")
        return None

    def extract_from_content(content) -> dict | None:
        if not content:
            return None
        parts = get_field(content, "parts")
        if not parts:
            return None
            
        for part in parts:
            res = extract_from_part(part)
            if res:
                return res
        return None

    # 1. Check current turn's user content
    if tool_context.user_content:
        res = extract_from_content(tool_context.user_content)
        if res:
            return res
        
    # 2. Check session history in reverse order
    if tool_context.session:
        events = get_field(tool_context.session, "events") or []
        for event in reversed(events):
            author = get_field(event, "author")
            if author == "user":
                content = get_field(event, "content")
                if content:
                    res = extract_from_content(content)
                    if res:
                        return res

    # 3. Check artifacts registered in the session
    try:
        artifact_keys = await tool_context.list_artifacts()
        midi_keys = [k for k in artifact_keys if k.lower().endswith((".mid", ".midi"))]
        if not midi_keys:
            midi_keys = artifact_keys
            
        for key in reversed(midi_keys):
            part = await tool_context.load_artifact(filename=key)
            if part:
                res = extract_from_part(part)
                if res:
                    res["fileName"] = key
                    return res
    except Exception as e:
        print(f"Failed to load or list artifacts: {e}")
        
    return None

async def import_midi_to_score(tool_context: ToolContext) -> str:
    """Imports an external MIDI file attachment from the chat into the active score state, overwriting the current score.

    Args:
        tool_context: The tool execution context containing session data and attachments.

    Returns:
        A JSON string containing the status, imported time/key signature, and part count.
    """
    script_path = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    session_id = tool_context.session.id

    file_attachment = await _extract_attachment_from_context(tool_context)
    if not file_attachment or not isinstance(file_attachment, dict):
        return json.dumps({"status": "error", "error": "No MIDI file attachment found in the chat."})
        
    b64_str = file_attachment.get("base64Data") or file_attachment.get("base64_data")
    if not b64_str:
        return json.dumps({"status": "error", "error": "Missing base64Data inside file_attachment."})

    try:
        content = _safe_decode_base64(b64_str)
        if not content.startswith(b"MThd"):
            return json.dumps({"status": "error", "error": "Invalid MIDI file: decoded content does not start with MThd header."})
        assets_dir = _PROJECT_ROOT / "skills" / "score_construction" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        uploaded_path = assets_dir / f"uploaded_{session_id}.mid"
        uploaded_path.write_bytes(content)
        resolved_path = str(uploaded_path.resolve())
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to decode base64 MIDI content: {e}"})

    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "import-midi", "--midi-path", resolved_path, "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from import-midi script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute import-midi script: {e}"})

async def analyze_midi_file(tool_context: ToolContext) -> str:
    """Ingests a raw binary MIDI file attachment from the chat and extracts track count, global tempo, note count, and detailed instrument listing.

    Args:
        tool_context: The tool execution context containing session data and attachments.

    Returns:
        A JSON string containing the status, track_count, tempo, note_count, list of instruments (names, programs, note counts), or error details.
    """
    script_path = _PROJECT_ROOT / "skills" / "midi_analytics" / "scripts" / "parse_midi_metrics.py"
    session_id = tool_context.session.id

    file_attachment = await _extract_attachment_from_context(tool_context)
    if not file_attachment or not isinstance(file_attachment, dict):
        return json.dumps({"status": "error", "error": "No MIDI file attachment found in the chat."})
        
    b64_str = file_attachment.get("base64Data") or file_attachment.get("base64_data")
    if not b64_str:
        return json.dumps({"status": "error", "error": "Missing base64Data inside file_attachment."})

    try:
        content = _safe_decode_base64(b64_str)
        if not content.startswith(b"MThd"):
            return json.dumps({"status": "error", "error": "Invalid MIDI file: decoded content does not start with MThd header."})
        assets_dir = _PROJECT_ROOT / "skills" / "midi_analytics" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        uploaded_path = assets_dir / f"uploaded_{session_id}.mid"
        uploaded_path.write_bytes(content)
        resolved_path = str(uploaded_path.resolve())
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to decode base64 MIDI content: {e}"})

    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "--file-path", resolved_path],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from midi parser script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute midi parser script: {e}"})

async def detect_key(tool_context: ToolContext) -> str:
    """Analyzes the active score session or an external MIDI file attachment in the chat to detect the musical key and confidence.

    Args:
        tool_context: The tool execution context containing session data.

    Returns:
        A JSON string containing the status, detected key, confidence score, and alternative keys.
    """
    script_path = _PROJECT_ROOT / "skills" / "music_theory_query" / "scripts" / "detect_key.py"
    session_id = tool_context.session.id

    file_attachment = await _extract_attachment_from_context(tool_context)

    resolved_path = ""
    if file_attachment:
        b64_str = file_attachment.get("base64Data") or file_attachment.get("base64_data")
        if b64_str:
            try:
                content = _safe_decode_base64(b64_str)
                if content.startswith(b"MThd"):
                    assets_dir = _PROJECT_ROOT / "skills" / "music_theory_query" / "assets"
                    assets_dir.mkdir(parents=True, exist_ok=True)
                    uploaded_path = assets_dir / f"uploaded_{session_id}.mid"
                    uploaded_path.write_bytes(content)
                    resolved_path = str(uploaded_path.resolve())
            except Exception:
                pass

    python_exe = sys.executable or "python"
    cmd = [python_exe, str(script_path)]
    if resolved_path:
        cmd.extend(["--midi-path", resolved_path])
    else:
        cmd.extend(["--session-id", session_id])
        
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from key detection script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute key detection script: {e}"})

def validate_voice_leading(tool_context: ToolContext) -> str:
    """Validates the active score session for voice-leading errors (parallel fifths/octaves) and vocal range violations.

    Args:
        tool_context: The tool execution context containing session data.

    Returns:
        A JSON string containing the status, violation status, and detailed list of parallel fifths, octaves, or range violations.
    """
    script_path = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "check_voice_leading.py"
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from voice leading checker script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute voice leading checker script: {e}"})

async def render_notation(tool_context: ToolContext, tracks: str = "", output_format: str = "") -> str:
    """Renders the current score state to visual piano roll and notation timeline graphs.

    Args:
        tool_context: The tool execution context containing session data.
        tracks: Optional comma-separated list of track IDs, names, or 1-based indices/ranges (e.g. 'piano', '1', '7-8') to render. If not specified, all tracks are rendered.
        output_format: Optional format filter. Only specify this if the user explicitly requests a single format (e.g., 'piano_roll' or 'musicxml'). Otherwise, leave empty to render all default views.

    Returns:
        A JSON string containing the status, piano_roll image path, notation_layout image path, score_plot image path, or error details.
    """
    script_path = _PROJECT_ROOT / "skills" / "visual_notation_rendering" / "scripts" / "generate_visuals.py"
    tracks = _sanitize_arg(tracks)
    output_format = _sanitize_arg(output_format)

    # Defensive check: if the model passed a format string to the tracks parameter
    if tracks.strip().lower() in ("piano_roll", "score_plot", "musicxml", "score_xml"):
        if not output_format:
            output_format = tracks
            tracks = ""

    session_id = tool_context.session.id
    python_exe = sys.executable or "python"
    cmd = [python_exe, str(script_path), "--session-id", session_id]
    if tracks:
        cmd.extend(["--tracks", tracks])
    if output_format:
        cmd.extend(["--format", output_format])

    assets_dir = _PROJECT_ROOT / "skills" / "visual_notation_rendering" / "assets"
    piano_roll_path = assets_dir / f"piano_roll_{session_id}.png"
    score_plot_path = assets_dir / f"score_plot_{session_id}.png"
    musicxml_path = assets_dir / f"score_{session_id}.musicxml"

    # Delete stale files from previous runs in the same session
    for path in (piano_roll_path, score_plot_path, musicxml_path):
        if path.is_file():
            try:
                path.unlink()
            except Exception:
                pass

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        
        # Load and save artifacts
        if result.returncode == 0:
            try:
                res_dict = json.loads(result.stdout)
            except Exception:
                res_dict = {"status": "success"}

            if piano_roll_path.is_file():
                with open(piano_roll_path, "rb") as f:
                    data = f.read()
                await tool_context.save_artifact(
                    filename=f"piano_roll_{session_id}.png",
                    artifact=types.Part.from_bytes(data=data, mime_type="image/png")
                )
                if "piano_roll" in res_dict:
                    res_dict["piano_roll_absolute"] = str(piano_roll_path.resolve().as_posix())
            
            if score_plot_path.is_file():
                with open(score_plot_path, "rb") as f:
                    data = f.read()
                await tool_context.save_artifact(
                    filename=f"score_plot_{session_id}.png",
                    artifact=types.Part.from_bytes(data=data, mime_type="image/png")
                )
                if "score_plot" in res_dict:
                    res_dict["score_plot_absolute"] = str(score_plot_path.resolve().as_posix())

            if musicxml_path.is_file():
                with open(musicxml_path, "rb") as f:
                    data = f.read()
                await tool_context.save_artifact(
                    filename=f"score_{session_id}.musicxml",
                    artifact=types.Part.from_bytes(data=data, mime_type="application/xml")
                )
                if "score_xml" in res_dict:
                    res_dict["musicxml_absolute"] = str(musicxml_path.resolve().as_posix())

            return json.dumps(res_dict, indent=2)

        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from rendering script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute rendering script: {e}"})

async def synthesize_score(tool_context: ToolContext, tracks: str = "", soundfont: str = "") -> str:
    """Synthesizes the current score state to a piano WAV audio file.

    Args:
        tool_context: The tool execution context containing session data.
        tracks: Optional comma-separated list of track IDs, names, or 1-based indices/ranges (e.g. 'piano', '1', '7-8') to play/synthesize. If not specified, all tracks are synthesized.
        soundfont: Optional soundfont filename to use for synthesis (e.g. 'TimGM6mb.sf2' or 'SalamanderGrandPiano-V3+20200602.sf2'). If not specified, defaults to TimGM6mb.sf2. Use list_soundfonts to see available options.

    Returns:
        A JSON string containing the status, audio_path to the synthesized WAV file, soundfont used, or error details.
    """
    script_path = _PROJECT_ROOT / "skills" / "acoustic_audio_synthesis" / "scripts" / "synthesize_score.py"
    tracks = _sanitize_arg(tracks)
    soundfont = _sanitize_arg(soundfont)
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    cmd = [python_exe, str(script_path), "--session-id", session_id]
    if tracks:
        cmd.extend(["--tracks", tracks])
    if soundfont:
        cmd.extend(["--soundfont", soundfont])
        
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        
        # Load and save WAV artifact if successful
        if result.returncode == 0:
            assets_dir = _PROJECT_ROOT / "skills" / "acoustic_audio_synthesis" / "assets"
            wav_path = assets_dir / f"score_{session_id}.wav"
            if wav_path.is_file():
                with open(wav_path, "rb") as f:
                    data = f.read()
                await tool_context.save_artifact(
                    filename=f"score_{session_id}.wav",
                    artifact=types.Part.from_bytes(data=data, mime_type="audio/wav")
                )
                try:
                    res_dict = json.loads(result.stdout)
                    res_dict["audio_path_absolute"] = str(wav_path.resolve().as_posix())
                    return json.dumps(res_dict, indent=2)
                except Exception:
                    pass
                
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from synthesis script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute synthesis script: {e}"})

def set_score_tempo(tool_context: ToolContext, bpm: float, offset: float = 0.0) -> str:
    """Sets/changes the tempo (in BPM) at a specific beat offset in the active score.

    Args:
        tool_context: The tool execution context containing session data.
        bpm: The tempo in beats per minute (BPM).
        offset: The beat offset at which this tempo applies (default 0.0 for start of score).

    Returns:
        A JSON string containing the status and details of the tempo setting.
    """
    script_path = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    cmd = [
        python_exe, str(script_path), "set-tempo",
        "--bpm", str(bpm),
        "--offset", str(offset),
        "--session-id", session_id
    ]
        
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from score manager script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute score manager script: {e}"})

def list_soundfonts() -> str:
    """Lists the available SoundFont (.sf2) files in the soundfonts/ directory and their descriptions.

    Returns:
        A JSON string containing the status and list of soundfonts with their names, sizes, and descriptions.
    """
    soundfonts_info = [
        {
            "filename": "TimGM6mb.sf2",
            "name": "TimGM6mb General MIDI SoundFont",
            "size": "6 MB",
            "description": "Standard General MIDI soundfont containing 128 instrumental patches (pianos, organs, guitars, strings, brass, drums, etc.). Good for full orchestration and multi-instrument arrangements.",
            "is_default": True
        },
        {
            "filename": "SalamanderGrandPiano-V3+20200602.sf2",
            "name": "Salamander Grand Piano",
            "size": "1.27 GB",
            "description": "High-fidelity, multi-velocity sampled Yamaha C5 grand piano. Ideal for high-quality solo piano or classical piano arrangements.",
            "is_default": False
        }
    ]
    return json.dumps({
        "status": "success",
        "soundfonts": soundfonts_info
    }, indent=2)

def list_soundfont_instruments() -> str:
    """Lists the available instruments / patches inside the General MIDI soundfont (TimGM6mb.sf2).

    Returns:
        A JSON string containing the list of categories and General MIDI instruments.
    """
    gm_instruments = {
        "Piano": {
            0: "Acoustic Grand Piano",
            1: "Bright Acoustic Piano",
            2: "Electric Grand Piano",
            3: "Honky-tonk Piano",
            4: "Electric Piano 1",
            5: "Electric Piano 2",
            6: "Harpsichord",
            7: "Clavinet"
        },
        "Chromatic Percussion": {
            8: "Celesta",
            9: "Glockenspiel",
            10: "Music Box",
            11: "Vibraphone",
            12: "Marimba",
            13: "Xylophone",
            14: "Tubular Bells",
            15: "Dulcimer"
        },
        "Organ": {
            16: "Drawbar Organ",
            17: "Percussive Organ",
            18: "Rock Organ",
            19: "Church Organ",
            20: "Reed Organ",
            21: "Accordion",
            22: "Harmonica",
            23: "Tango Accordion"
        },
        "Guitar": {
            24: "Acoustic Guitar (nylon)",
            25: "Acoustic Guitar (steel)",
            26: "Electric Guitar (jazz)",
            27: "Electric Guitar (clean)",
            28: "Electric Guitar (muted)",
            29: "Overdriven Guitar",
            30: "Distortion Guitar",
            31: "Guitar harmonics"
        },
        "Bass": {
            32: "Acoustic Bass",
            33: "Electric Bass (finger)",
            34: "Electric Bass (pick)",
            35: "Fretless Bass",
            36: "Slap Bass 1",
            37: "Slap Bass 2",
            38: "Synth Bass 1",
            39: "Synth Bass 2"
        },
        "Strings": {
            40: "Violin",
            41: "Viola",
            42: "Cello",
            43: "Contrabass",
            44: "Tremolo Strings",
            45: "Pizzicato Strings",
            46: "Orchestral Harp",
            47: "Timpani"
        },
        "Ensemble": {
            48: "String Ensemble 1",
            49: "String Ensemble 2",
            50: "Synth Strings 1",
            51: "Synth Strings 2",
            52: "Choir Aahs",
            53: "Voice Oohs",
            54: "Synth Voice",
            55: "Orchestra Hit"
        },
        "Brass": {
            56: "Trumpet",
            57: "Trombone",
            58: "Tuba",
            59: "Muted Trumpet",
            60: "French Horn",
            61: "Brass Section",
            62: "Synth Brass 1",
            63: "Synth Brass 2"
        },
        "Reed": {
            64: "Soprano Sax",
            65: "Alto Sax",
            66: "Tenor Sax",
            67: "Baritone Sax",
            68: "Oboe",
            69: "English Horn",
            70: "Bassoon",
            71: "Clarinet"
        },
        "Pipe": {
            72: "Piccolo",
            73: "Flute",
            74: "Recorder",
            75: "Pan Flute",
            76: "Blown Bottle",
            77: "Shakuhachi",
            78: "Whistle",
            79: "Ocarina"
        },
        "Synth Lead": {
            80: "Lead 1 (square)",
            81: "Lead 2 (sawtooth)",
            82: "Lead 3 (calliope)",
            83: "Lead 4 (chiff)",
            84: "Lead 5 (charang)",
            85: "Lead 6 (voice)",
            86: "Lead 7 (fifths)",
            87: "Lead 8 (bass + lead)"
        },
        "Synth Pad": {
            88: "Pad 1 (new age)",
            89: "Pad 2 (warm)",
            90: "Pad 3 (polysynth)",
            91: "Pad 4 (choir)",
            92: "Pad 5 (bowed)",
            93: "Pad 6 (metallic)",
            94: "Pad 7 (halo)",
            95: "Pad 8 (sweep)"
        },
        "Synth Effects": {
            96: "FX 1 (rain)",
            97: "FX 2 (soundtrack)",
            98: "FX 3 (crystal)",
            99: "FX 4 (atmosphere)",
            100: "FX 5 (brightness)",
            101: "FX 6 (goblins)",
            102: "FX 7 (echoes)",
            103: "FX 8 (sci-fi)"
        },
        "Ethnic": {
            104: "Sitar",
            105: "Banjo",
            106: "Shamisen",
            107: "Koto",
            108: "Kalimba",
            109: "Bagpipe",
            110: "Fiddle",
            111: "Shanai"
        },
        "Percussive": {
            112: "Tinkle Bell",
            113: "Agogo",
            114: "Steel Drums",
            115: "Woodblock",
            116: "Taiko Drum",
            117: "Melodic Tom",
            118: "Synth Drum",
            119: "Reverse Cymbal"
        },
        "Sound Effects": {
            120: "Guitar Fret Noise",
            121: "Breath Noise",
            122: "Seashore",
            123: "Bird Tweet",
            124: "Telephone Ring",
            125: "Helicopter",
            126: "Applause",
            127: "Gunshot"
        }
    }
    return json.dumps({
        "status": "success",
        "soundfont": "TimGM6mb.sf2",
        "instrument_categories": gm_instruments
    }, indent=2)

def assign_instrument_to_track(tool_context: ToolContext, part_id: str, program: int, is_percussion: bool = False) -> str:
    """Manually assigns a specific General MIDI instrument (program number 0-127) to a track/part in the active score.

    Args:
        tool_context: The tool execution context containing session data.
        part_id: The ID of the part/track (e.g. 'melody', 'part_1').
        program: The MIDI program number (0-127) for the instrument.
        is_percussion: Set to True if this track is unpitched drums/percussion.

    Returns:
        A JSON string containing the status and details of the assignment.
    """
    script_path = _PROJECT_ROOT / "skills" / "score_construction" / "scripts" / "score_manager.py"
    part_id = _sanitize_arg(part_id)
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    cmd = [
        python_exe, str(script_path), "assign-instrument",
        "--part-id", part_id,
        "--program", str(program),
        "--session-id", session_id
    ]
    if is_percussion:
        cmd.append("--percussion")
        
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from score manager script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute score manager script: {e}"})

root_agent = Agent(
    name="music_assistant_root",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are Cadence, an AI music assistant designed to help with music theory, chords, scores, and MIDI files.\n"
        "When a user attaches or uploads any file (including generic binary attachments or files with MIME types like application/octet-stream) and requests a music task (such as import, analyze, play, or key detection), you must assume it is the MIDI file they want to process. You must call the appropriate tool (such as analyze_midi_file, import_midi_to_score, or detect_key) immediately on the very first turn. Under standard ADK tool integration, the chat attachment's media data will be mapped directly to the tool's structured file_attachment parameter. Do not ask the user to attach a MIDI file if they have already uploaded a file in their message.\n"
        "Use the evaluate_interval tool to compute pitch distance and interval names.\n"
        "Use the list_scale_pitches tool to generate the notes/pitches of a specific scale or mode (major, minor, dorian, phrygian, lydian, mixolydian, locrian).\n"
        "Use the analyze_chord tool to verify chord spellings, identify a chord's common name, and optionally perform Roman numeral analysis in a given key.\n"
        "Use the render_chord_diagram tool to render a visual keyboard (piano) or fretboard (guitar) diagram for a chord. When the user asks to visualize a chord or when you are answering a theory question about chord voicings/structures, call render_chord_diagram to generate a visual aid and embed the resulting PNG in your response as an inline markdown image using the exact 'output_path' returned by the tool (e.g., ![Chord Diagram](skills/visual_notation_rendering/assets/chord_xyz.png)), replacing the filename with the actual one returned by the tool.\n"
        "Use the detect_key tool to estimate/detect the key signature of the active score or a MIDI file.\n"
        "Use the initialize_score, add_note_to_score, and add_abc_to_score tools to manage and construct symbolic scores. Prefer add_abc_to_score when the user wants to enter multiple notes or a melody line quickly using ABC notation or TinyNotation. Use delete_note_from_score to remove or replace notes/rests, edit_note_in_score to edit pitches/durations of existing notes, insert_measure_into_score to insert blank measures, and delete_measure_from_score to remove measures.\n"
        "Use the transpose_score tool to transpose all notes/chords and key signatures in the active score up or down by a given number of semitones. Use transpose_part_in_score to transpose a single part/track in the score.\n"
        "Use the validate_voice_leading tool to check the active score for classical voice-leading violations (parallel fifths/octaves) and range errors.\n"
        "Use the export_score_to_midi tool to export the active score to a standard MIDI file. When exporting MIDI, notify the user that the MIDI file is ready. Do not output any file:// links in your response. The chat UI will automatically attach the generated MIDI file inline for the user to download.\n"
        "Use the import_midi_to_score tool to load an external MIDI file into the active score session. When you run import_midi_to_score, you MUST list the automatically assigned instruments for all tracks in your response to the user. "
        "Additionally, if the tool returns any tracks in 'uncertain_parts' (meaning they defaulted to Acoustic Grand Piano (0) but their track names suggest they might be different instruments), you MUST ask the user for clarification about which General MIDI instruments they want to assign to those tracks.\n"
        "Use the list_soundfonts tool to view available soundfont files and their descriptions.\n"
        "Use the list_soundfont_instruments tool to view all 128 General MIDI instrument programs and categories. You can search these program names to suggest appropriate instruments (e.g. various guitar patches) when users want to re-assign tracks.\n"
        "Use the assign_instrument_to_track tool to manually assign a specific General MIDI instrument (program number 0-127) and optionally flag it as unpitched percussion for a given part_id in the score.\n"
        "Use the set_score_tempo tool to set or change the tempo (in BPM) at a specific beat offset in the active score.\n"
        "Use the analyze_midi_file tool to ingest raw MIDI files and extract track count, tempo, note count, and detailed instrument track information.\n"
        "Use the render_notation tool to visualize the current score state as piano roll and timeline notation graphs. You can optionally filter which tracks are rendered/exported by passing a comma-separated list of track IDs, names, or 1-based indices/ranges (e.g. 'piano', '1', '7-8') to the tracks parameter. Do not specify the output_format parameter unless the user explicitly requests only a single format. "
        "When rendering visual notation, if the user explicitly requested a piano roll, visualization, or plot, you MUST return the actual paths of the generated image assets (piano_roll, score_plot) returned by the tool formatted as inline Markdown image links, for example: "
        "![Piano Roll](skills/visual_notation_rendering/assets/piano_roll_<session_id>.png) and ![Score Plot](skills/visual_notation_rendering/assets/score_plot_<session_id>.png) (using the actual session ID from the tool response), and you MUST also explicitly notify the user that the generated MusicXML file is ready for MuseScore inspection by including the exact path of the generated MusicXML file (skills/visual_notation_rendering/assets/score_<session_id>.musicxml) in your text response. "
        "Otherwise, if the user only requested sheet music or a MusicXML file, you MUST NOT embed the piano roll images in your response, and you MUST only explicitly notify the user that the high-fidelity MusicXML asset is ready. Do not output any file:// links in your response. The chat UI will automatically attach the generated MusicXML file inline for the user to download.\n"
        "Use the synthesize_score tool to compile the notes from the score state into a WAV audio file. You can optionally filter which tracks are played/synthesized by passing a comma-separated list of track IDs, names, or 1-based indices/ranges (e.g. 'piano', '1', '7-8') to the tracks parameter. "
        "You can also pass a soundfont filename to the soundfont parameter to choose which .sf2 soundfont is used for synthesis (e.g. 'TimGM6mb.sf2' for General MIDI, or 'SalamanderGrandPiano-V3+20200602.sf2' for the high-quality grand piano). If the user asks for a specific instrument or soundfont and you are unsure of the exact filename, call list_soundfonts first. "
        "When synthesizing audio, notify the user that the audio is ready. Do not output any file:// links in your response. The chat UI will automatically attach the generated WAV file inline for the user to play or download. Also mention which soundfont was used (it is returned in the tool response as 'soundfont').\n"
        "IMPORTANT: If the user requests to 'export' the score without specifying a format, you MUST clarify whether they want a MIDI file (using export_score_to_midi) or visual notation/sheet music (using render_notation)."
    ),
    tools=[
        evaluate_interval,
        list_scale_pitches,
        analyze_chord,
        render_chord_diagram,
        detect_key,
        initialize_score,
        add_note_to_score,
        add_abc_to_score,
        transpose_score,
        validate_voice_leading,
        export_score_to_midi,
        import_midi_to_score,
        analyze_midi_file,
        list_soundfonts,
        list_soundfont_instruments,
        assign_instrument_to_track,
        set_score_tempo,
        render_notation,
        synthesize_score,
        delete_note_from_score,
        edit_note_in_score,
        insert_measure_into_score,
        delete_measure_from_score,
        transpose_part_in_score
    ],
)

app = App(
    root_agent=root_agent,
    name="agents",
)
