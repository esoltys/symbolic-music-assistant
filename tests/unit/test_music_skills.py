import sys
import json
import subprocess
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

def run_script(script_relative_path, args):
    script_path = PROJECT_ROOT / script_relative_path
    python_exe = sys.executable or "python"
    result = subprocess.run(
        [python_exe, str(script_path)] + args,
        capture_output=True,
        text=True,
        check=False
    )
    return result

def test_list_scale_pitches():
    # Test valid major scale
    res = run_script("skills/music_theory_query/scripts/list_scale_pitches.py", ["C", "major"])
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["status"] == "success"
    assert data["pitches"] == ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]

    # Test valid dorian scale
    res = run_script("skills/music_theory_query/scripts/list_scale_pitches.py", ["D", "dorian"])
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["status"] == "success"
    assert data["pitches"] == ["D4", "E4", "F4", "G4", "A4", "B4", "C5", "D5"]

    # Test invalid scale
    res = run_script("skills/music_theory_query/scripts/list_scale_pitches.py", ["C", "invalid_mode"])
    assert res.returncode != 0
    data = json.loads(res.stdout)
    assert data["status"] == "error"

def test_analyze_chord():
    # Test major triad without key
    res = run_script("skills/music_theory_query/scripts/analyze_chord.py", ["C4,E4,G4"])
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["status"] == "success"
    assert "major triad" in data["common_name"]
    assert data["is_triad"] is True
    assert data["inversion"] == 0

    # Test minor seventh chord with key Roman numeral
    res = run_script("skills/music_theory_query/scripts/analyze_chord.py", ["C4,E-4,G4,B-4", "--key", "E- Major"])
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["status"] == "success"
    assert "minor seventh" in data["common_name"]
    assert data["roman_numeral"] == "vi7"

def test_score_manager_new_subcommands():
    session_id = "test_unit_sess"
    
    # 1. Init score
    res = run_script("skills/score_construction/scripts/score_manager.py", ["init", "--time-signature", "4/4", "--key-signature", "C Major", "--session-id", session_id])
    assert res.returncode == 0
    
    # 2. Add notes
    res = run_script("skills/score_construction/scripts/score_manager.py", ["add", "--pitch", "C4,E4,G4", "--duration", "half", "--session-id", session_id])
    assert res.returncode == 0
    
    # 3. Transpose score
    res = run_script("skills/score_construction/scripts/score_manager.py", ["transpose", "--semitones", "2", "--session-id", session_id])
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["status"] == "success"
    assert data["new_key_signature"] == "D Major"
    
    # Verify file content
    state_file = PROJECT_ROOT / "skills" / "score_construction" / "assets" / f"score_{session_id}.json"
    assert state_file.is_file()
    with open(state_file, "r") as f:
        state = json.load(f)
    assert state["key_signature"] == "D Major"
    assert state["parts"][0]["measures"][0]["events"][0]["pitches"] == ["D4", "F#4", "A4"]
    
    # 4. Export to MIDI
    res = run_script("skills/score_construction/scripts/score_manager.py", ["export-midi", "--session-id", session_id])
    assert res.returncode == 0
    midi_path = PROJECT_ROOT / "skills" / "score_construction" / "assets" / f"score_{session_id}.mid"
    assert midi_path.is_file()
    
    # 5. Import from MIDI
    import_session_id = "test_unit_import"
    res = run_script("skills/score_construction/scripts/score_manager.py", [
        "import-midi",
        "--midi-path", str(midi_path),
        "--session-id", import_session_id
    ])
    assert res.returncode == 0
    
    # Verify imported file content
    import_file = PROJECT_ROOT / "skills" / "score_construction" / "assets" / f"score_{import_session_id}.json"
    assert import_file.is_file()
    with open(import_file, "r") as f:
        imported_state = json.load(f)
    assert imported_state["key_signature"] == "D Major"
    assert imported_state["parts"][0]["measures"][0]["events"][0]["pitches"] == ["D4", "F#4", "A4"]
    
    # Cleanup files
    state_file.unlink(missing_ok=True)
    midi_path.unlink(missing_ok=True)
    import_file.unlink(missing_ok=True)
