import sys
import subprocess
import json
from pathlib import Path
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

def evaluate_interval(start_note: str, end_note: str) -> str:
    """Calculates the semitone distance and canonical interval name between two note pitches.

    Args:
        start_note: The starting note name (e.g., 'C4', 'E-3', 'F#5').
        end_note: The ending note name (e.g., 'G4', 'D6', 'B#2').

    Returns:
        A JSON string containing the status, calculated semitones, interval name, or error details.
    """
    # Locate evaluate_intervals.py relative to the project root
    project_root = Path(__file__).parent.parent.parent.resolve()
    script_path = project_root / "skills" / "music_theory_query" / "scripts" / "evaluate_intervals.py"
    
    # Use the active virtual environment's python interpreter to run the script
    python_exe = sys.executable or "python"
    
    try:
        result = subprocess.run(
            [python_exe, str(script_path), start_note, end_note],
            capture_output=True,
            text=True,
            check=False
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from execution script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute interval calculation script: {e}"})

def initialize_canvas(time_signature: str = "4/4") -> str:
    """Initializes a fresh localized musical score canvas.

    Args:
        time_signature: The time signature for the score (default: '4/4').

    Returns:
        A JSON string containing the status, time_signature, and notes_count.
    """
    project_root = Path(__file__).parent.parent.parent.resolve()
    script_path = project_root / "skills" / "score_construction" / "scripts" / "canvas_manager.py"
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "init", "--time-signature", time_signature],
            capture_output=True,
            text=True,
            check=False
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from canvas script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute canvas manager script: {e}"})

def add_note_to_canvas(pitch: str, duration: str) -> str:
    """Adds/appends a note or rest token sequentially to the active score canvas.

    Args:
        pitch: The note name (e.g. 'C4', 'E-3', 'F#5') or 'rest' for a rest token.
        duration: The duration of the token (e.g. 'quarter', 'half', 'eighth', 'whole').

    Returns:
        A JSON string containing the status, added note details, and updated notes_count.
    """
    project_root = Path(__file__).parent.parent.parent.resolve()
    script_path = project_root / "skills" / "score_construction" / "scripts" / "canvas_manager.py"
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "add", "--pitch", pitch, "--duration", duration],
            capture_output=True,
            text=True,
            check=False
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from canvas script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute canvas manager script: {e}"})

def analyze_midi_file(file_path: str) -> str:
    """Ingests a raw binary MIDI file and extracts track count, global tempo, and note count.

    Args:
        file_path: The local path to the MIDI file to analyze.

    Returns:
        A JSON string containing the status, track_count, tempo, note_count, or error details.
    """
    project_root = Path(__file__).parent.parent.parent.resolve()
    script_path = project_root / "skills" / "midi_analytics" / "scripts" / "parse_midi_metrics.py"
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "--file-path", file_path],
            capture_output=True,
            text=True,
            check=False
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from midi parser script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute midi parser script: {e}"})

root_agent = Agent(
    name="music_assistant_root",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are a symbolic music assistant designed to help with music theory, chords, scores, and MIDI files. "
        "Use the evaluate_interval tool to compute pitch distance and interval names. "
        "Use the initialize_canvas and add_note_to_canvas tools to manage and construct symbolic scores on the canvas. "
        "Use the analyze_midi_file tool to ingest raw MIDI files and extract track count, tempo, and note count."
    ),
    tools=[evaluate_interval, initialize_canvas, add_note_to_canvas, analyze_midi_file],
)

app = App(
    root_agent=root_agent,
    name="music_assistant",
)


