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

def test_detect_key():
    temp_score_path = PROJECT_ROOT / "skills" / "score_construction" / "assets" / "score_temp_key_test.json"
    temp_score_path.parent.mkdir(parents=True, exist_ok=True)
    
    score_state = {
        "time_signature": "4/4",
        "key_signature": "C Major",
        "parts": [
            {
                "id": "melody",
                "name": "Melody",
                "clef": "treble",
                "measures": [
                    {
                        "number": 1,
                        "events": [
                            {"pitches": ["G4"], "duration": "quarter"},
                            {"pitches": ["B4"], "duration": "quarter"},
                            {"pitches": ["D5"], "duration": "quarter"},
                            {"pitches": ["F#5"], "duration": "quarter"}
                        ]
                    }
                ]
            }
        ]
    }
    
    with open(temp_score_path, "w", encoding="utf-8") as f:
        json.dump(score_state, f)
        
    try:
        res = run_script("skills/music_theory_query/scripts/detect_key.py", ["--score-path", str(temp_score_path)])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert data["status"] == "success"
        assert "G" in data["detected_key"] or "E" in data["detected_key"]
    finally:
        temp_score_path.unlink(missing_ok=True)

def test_parse_midi_metrics():
    sample_midi = PROJECT_ROOT / "skills" / "midi_analytics" / "assets" / "sample.mid"
    assert sample_midi.is_file()
    
    # Run parse_midi_metrics on the tracked sample.mid
    res_parse = run_script("skills/midi_analytics/scripts/parse_midi_metrics.py", ["--file-path", str(sample_midi)])
    assert res_parse.returncode == 0
    data = json.loads(res_parse.stdout)
    assert data["status"] == "success"
    assert data["track_count"] == 1
    assert data["tempo"] == 120.0
    assert data["note_count"] == 256
    assert len(data["instruments"]) == 1
    assert data["instruments"][0]["instrument"] == "Acoustic Grand Piano"
    assert data["instruments"][0]["note_count"] == 256

def test_voice_leading():
    temp_score_path = PROJECT_ROOT / "skills" / "score_construction" / "assets" / "score_temp_voice_leading.json"
    temp_score_path.parent.mkdir(parents=True, exist_ok=True)
    
    score_state = {
        "time_signature": "4/4",
        "key_signature": "C Major",
        "parts": [
            {
                "id": "soprano",
                "name": "Soprano",
                "clef": "treble",
                "measures": [
                    {
                        "number": 1,
                        "events": [
                            {"pitches": ["C5"], "duration": "half"},
                            {"pitches": ["D5"], "duration": "half"}
                        ]
                    }
                ]
            },
            {
                "id": "bass",
                "name": "Bass",
                "clef": "bass",
                "measures": [
                    {
                        "number": 1,
                        "events": [
                            {"pitches": ["F3"], "duration": "half"},
                            {"pitches": ["G3"], "duration": "half"}
                        ]
                    }
                ]
            }
        ]
    }
    
    with open(temp_score_path, "w", encoding="utf-8") as f:
        json.dump(score_state, f)
        
    try:
        res = run_script("skills/score_construction/scripts/check_voice_leading.py", ["--score-path", str(temp_score_path)])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert data["status"] == "success"
        assert data["has_violations"] is True
        assert len(data["violations"]["parallel_fifths"]) == 1
    finally:
        temp_score_path.unlink(missing_ok=True)

    # Now test voice range violation
    score_state_range = {
        "time_signature": "4/4",
        "key_signature": "C Major",
        "parts": [
            {
                "id": "soprano",
                "name": "Soprano",
                "clef": "treble",
                "measures": [
                    {
                        "number": 1,
                        "events": [
                            {"pitches": ["C3"], "duration": "whole"}
                        ]
                    }
                ]
            }
        ]
    }
    
    with open(temp_score_path, "w", encoding="utf-8") as f:
        json.dump(score_state_range, f)
        
    try:
        res = run_script("skills/score_construction/scripts/check_voice_leading.py", ["--score-path", str(temp_score_path)])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert data["status"] == "success"
        assert data["has_violations"] is True
        assert len(data["violations"]["range_violations"]) == 1
        assert "Soprano" in data["violations"]["range_violations"][0]["profile"]
    finally:
        temp_score_path.unlink(missing_ok=True)



