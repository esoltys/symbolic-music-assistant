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

root_agent = Agent(
    name="music_assistant_root",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="You are a symbolic music assistant designed to help with music theory, chords, scores, and MIDI files. Use the evaluate_interval tool to compute pitch distance and interval names.",
    tools=[evaluate_interval],
)

app = App(
    root_agent=root_agent,
    name="music_assistant",
)

