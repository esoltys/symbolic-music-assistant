import sys
import subprocess
import json
from pathlib import Path
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types
from google.adk.tools import ToolContext

def evaluate_interval(start_note: str, end_note: str) -> str:
    """Calculates the semitone distance and canonical interval name between two note pitches.

    Args:
        start_note: The starting note name (e.g., 'C4', 'E-3', 'F#5').
        end_note: The ending note name (e.g., 'G4', 'D6', 'B#2').

    Returns:
        A JSON string containing the status, calculated semitones, interval name, or error details.
    """
    project_root = Path(__file__).parent.parent.parent.resolve()
    script_path = project_root / "skills" / "music_theory_query" / "scripts" / "evaluate_intervals.py"
    
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

def list_scale_pitches(tonic: str, scale_type: str) -> str:
    """Generates the notes/pitches of a specific scale or mode.

    Args:
        tonic: The tonic note name (e.g., 'C', 'F#', 'B-').
        scale_type: The scale/mode type (e.g., 'major', 'minor', 'dorian', 'phrygian', 'lydian', 'mixolydian', 'locrian').

    Returns:
        A JSON string containing the status, tonic, scale type, and list of pitches.
    """
    project_root = Path(__file__).parent.parent.parent.resolve()
    script_path = project_root / "skills" / "music_theory_query" / "scripts" / "list_scale_pitches.py"
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), tonic, scale_type],
            capture_output=True,
            text=True,
            check=False
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
    project_root = Path(__file__).parent.parent.parent.resolve()
    script_path = project_root / "skills" / "music_theory_query" / "scripts" / "analyze_chord.py"
    
    python_exe = sys.executable or "python"
    cmd = [python_exe, str(script_path), pitches]
    if key_signature:
        cmd.extend(["--key", key_signature])
        
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from chord analysis script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute chord analysis script: {e}"})

def initialize_score(tool_context: ToolContext, time_signature: str = "4/4", key_signature: str = "C Major") -> str:
    """Initializes a fresh localized musical score.

    Args:
        tool_context: The tool execution context containing session data.
        time_signature: The time signature for the score (default: '4/4').
        key_signature: The key signature for the score (default: 'C Major').

    Returns:
        A JSON string containing the status, time_signature, key_signature, and parts_count.
    """
    project_root = Path(__file__).parent.parent.parent.resolve()
    script_path = project_root / "skills" / "score_construction" / "scripts" / "score_manager.py"
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "init", "--time-signature", time_signature, "--key-signature", key_signature, "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False
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
    project_root = Path(__file__).parent.parent.parent.resolve()
    script_path = project_root / "skills" / "score_construction" / "scripts" / "score_manager.py"
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "add", "--pitch", pitch, "--duration", duration, "--part-id", part_id, "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False
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
    project_root = Path(__file__).parent.parent.parent.resolve()
    script_path = project_root / "skills" / "score_construction" / "scripts" / "score_manager.py"
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "transpose", "--semitones", str(semitones), "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from score transposition script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute score transposition script: {e}"})

async def export_score_to_midi(tool_context: ToolContext) -> str:
    """Exports the active score session to a standard MIDI (.mid) file and saves it as an artifact.

    Args:
        tool_context: The tool execution context containing session data.

    Returns:
        A JSON string containing the status, midi_path of the generated file, or error details.
    """
    project_root = Path(__file__).parent.parent.parent.resolve()
    script_path = project_root / "skills" / "score_construction" / "scripts" / "score_manager.py"
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "export-midi", "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False
        )
        
        # Load and save MIDI artifact if successful
        if result.returncode == 0:
            assets_dir = project_root / "skills" / "score_construction" / "assets"
            midi_path = assets_dir / f"score_{session_id}.mid"
            if midi_path.is_file():
                with open(midi_path, "rb") as f:
                    data = f.read()
                await tool_context.save_artifact(
                    filename=f"score_{session_id}.mid",
                    artifact=types.Part.from_bytes(data=data, mime_type="audio/midi")
                )
                
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from export-midi script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute export-midi script: {e}"})

def import_midi_to_score(tool_context: ToolContext, midi_path: str) -> str:
    """Imports an external MIDI file into the active score state, overwriting the current score.

    Args:
        tool_context: The tool execution context containing session data.
        midi_path: The local path to the MIDI file to import.

    Returns:
        A JSON string containing the status, imported time/key signature, and part count.
    """
    project_root = Path(__file__).parent.parent.parent.resolve()
    script_path = project_root / "skills" / "score_construction" / "scripts" / "score_manager.py"
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "import-midi", "--midi-path", midi_path, "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False
        )
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from import-midi script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute import-midi script: {e}"})

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

async def render_notation(tool_context: ToolContext) -> str:
    """Renders the current score state to visual piano roll and notation timeline graphs.

    Args:
        tool_context: The tool execution context containing session data.

    Returns:
        A JSON string containing the status, piano_roll image path, notation_layout image path, score_plot image path, or error details.
    """
    project_root = Path(__file__).parent.parent.parent.resolve()
    script_path = project_root / "skills" / "visual_notation_rendering" / "scripts" / "generate_visuals.py"
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False
        )
        
        # Load and save artifacts
        if result.returncode == 0:
            assets_dir = project_root / "skills" / "visual_notation_rendering" / "assets"
            piano_roll_path = assets_dir / f"piano_roll_{session_id}.png"
            score_plot_path = assets_dir / f"score_plot_{session_id}.png"
            musicxml_path = assets_dir / f"score_{session_id}.musicxml"

            if piano_roll_path.is_file():
                with open(piano_roll_path, "rb") as f:
                    data = f.read()
                await tool_context.save_artifact(
                    filename=f"piano_roll_{session_id}.png",
                    artifact=types.Part.from_bytes(data=data, mime_type="image/png")
                )
            
            if score_plot_path.is_file():
                with open(score_plot_path, "rb") as f:
                    data = f.read()
                await tool_context.save_artifact(
                    filename=f"score_plot_{session_id}.png",
                    artifact=types.Part.from_bytes(data=data, mime_type="image/png")
                )

            if musicxml_path.is_file():
                with open(musicxml_path, "rb") as f:
                    data = f.read()
                await tool_context.save_artifact(
                    filename=f"score_{session_id}.musicxml",
                    artifact=types.Part.from_bytes(data=data, mime_type="application/xml")
                )

        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from rendering script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute rendering script: {e}"})

async def synthesize_score(tool_context: ToolContext) -> str:
    """Synthesizes the current score state to a piano WAV audio file.

    Args:
        tool_context: The tool execution context containing session data.

    Returns:
        A JSON string containing the status, audio_path to the synthesized WAV file, or error details.
    """
    project_root = Path(__file__).parent.parent.parent.resolve()
    script_path = project_root / "skills" / "acoustic_audio_synthesis" / "scripts" / "synthesize_score.py"
    session_id = tool_context.session.id
    
    python_exe = sys.executable or "python"
    try:
        result = subprocess.run(
            [python_exe, str(script_path), "--session-id", session_id],
            capture_output=True,
            text=True,
            check=False
        )
        
        # Load and save WAV artifact if successful
        if result.returncode == 0:
            assets_dir = project_root / "skills" / "acoustic_audio_synthesis" / "assets"
            wav_path = assets_dir / f"score_{session_id}.wav"
            if wav_path.is_file():
                with open(wav_path, "rb") as f:
                    data = f.read()
                await tool_context.save_artifact(
                    filename=f"score_{session_id}.wav",
                    artifact=types.Part.from_bytes(data=data, mime_type="audio/wav")
                )
                
        return (result.stdout or result.stderr or 
                json.dumps({"status": "error", "error": "No output from synthesis script."}))
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Failed to execute synthesis script: {e}"})

root_agent = Agent(
    name="music_assistant_root",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are a symbolic music assistant designed to help with music theory, chords, scores, and MIDI files.\n"
        "Use the evaluate_interval tool to compute pitch distance and interval names.\n"
        "Use the list_scale_pitches tool to generate the notes/pitches of a specific scale or mode (major, minor, dorian, phrygian, lydian, mixolydian, locrian).\n"
        "Use the analyze_chord tool to identify a chord's common name and optionally perform Roman numeral analysis in a given key.\n"
        "Use the initialize_score and add_note_to_score tools to manage and construct symbolic scores.\n"
        "Use the transpose_score tool to transpose all notes/chords and key signatures in the active score up or down by a given number of semitones.\n"
        "Use the export_score_to_midi tool to export the active score to a standard MIDI file. When exporting MIDI, you MUST return the actual path of the generated MIDI asset returned by the tool (e.g., `skills/score_construction/assets/score_<session_id>.mid`) in your final response.\n"
        "Use the import_midi_to_score tool to load an external MIDI file into the active score session. When importing a MIDI file, notify the user that the score has been updated, and suggest visualizing or synthesizing it.\n"
        "Use the analyze_midi_file tool to ingest raw MIDI files and extract track count, tempo, and note count.\n"
        "Use the render_notation tool to visualize the current score state as piano roll and timeline notation graphs. "
        "When rendering visual notation, you MUST return the actual paths of the generated image assets (piano_roll, score_plot) returned by the tool formatted as inline Markdown image links, for example: "
        "![Piano Roll](skills/visual_notation_rendering/assets/piano_roll_<session_id>.png) and ![Score Plot](skills/visual_notation_rendering/assets/score_plot_<session_id>.png) (using the actual session ID from the tool response). "
        "Additionally, you MUST explicitly notify the user that the high-fidelity MusicXML asset is ready for MuseScore inspection, including its actual file path returned by the tool (e.g., `skills/visual_notation_rendering/assets/score_<session_id>.musicxml`).\n"
        "Use the synthesize_score tool to compile the notes from the score state into a piano WAV audio file. "
        "When synthesizing audio, you MUST return the actual path of the generated audio asset returned by the tool (e.g., `skills/acoustic_audio_synthesis/assets/score_<session_id>.wav`) in your final response."
    ),
    tools=[
        evaluate_interval,
        list_scale_pitches,
        analyze_chord,
        initialize_score,
        add_note_to_score,
        transpose_score,
        export_score_to_midi,
        import_midi_to_score,
        analyze_midi_file,
        render_notation,
        synthesize_score
    ],
)

app = App(
    root_agent=root_agent,
    name="agents",
)
