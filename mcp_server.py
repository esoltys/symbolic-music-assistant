"""MCP server for Cadence — Music Theory Tools.

Exposes the three stateless music-theory tools as a Model Context Protocol (MCP)
server so that external MCP clients (e.g. Claude Desktop, other ADK agents, or
any MCP-compatible application) can call them directly without running the full
assistant agent.

Exposed tools
-------------
* evaluate_interval  — compute semitone distance and interval name between two pitches
* list_scale_pitches — spell a scale or mode (major, minor, dorian, …)
* analyze_chord      — identify a chord's name, inversion, triad status, and Roman numeral

Usage
-----
Run the server (stdio transport, compatible with Claude Desktop):

    uv run python mcp_server.py

Or from the agents-cli playground, connect to it as an MCP tool source.

See README.md for Claude Desktop configuration instructions.
"""

import sys
import subprocess
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Security helpers (mirrors agents/music_assistant/agent.py)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent.resolve()
_MAX_ARG_LEN = 256


def _safe_resolve_path(user_path: str) -> str | None:
    """Resolve a user-supplied file path and verify it lies inside the project root.

    Prevents directory traversal: a crafted path like '../../etc/passwd' will
    fail the relative_to() check and return None.
    """
    if not user_path:
        return None
    try:
        resolved = Path(user_path).resolve()
        resolved.relative_to(_PROJECT_ROOT)
        return str(resolved)
    except (ValueError, OSError):
        return None


def _sanitize_arg(value: str, max_len: int = _MAX_ARG_LEN) -> str:
    """Truncate a string argument to a safe maximum length."""
    return value[:max_len]


# ---------------------------------------------------------------------------
# FastMCP server definition
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="cadence-music-theory",
    instructions=(
        "A music theory MCP server for Cadence, the AI music assistant. "
        "Provides three stateless tools: evaluate_interval, list_scale_pitches, "
        "and analyze_chord. All tools use music21 under the hood."
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
        )
        return result.stdout or result.stderr or json.dumps(
            {"status": "error", "error": "No output from script."}
        )
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
