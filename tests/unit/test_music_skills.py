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


def test_midi_attachments():
    import asyncio
    from unittest.mock import MagicMock, AsyncMock
    from agents.music_assistant.agent import analyze_midi_file, import_midi_to_score, detect_key
    
    sample_midi_path = PROJECT_ROOT / "skills" / "midi_analytics" / "assets" / "sample.mid"
    assert sample_midi_path.is_file()
    sample_midi_bytes = sample_midi_path.read_bytes()
    
    mock_part = MagicMock()
    mock_part.inline_data = MagicMock()
    mock_part.inline_data.mime_type = "audio/midi"
    mock_part.inline_data.data = sample_midi_bytes
    mock_part.file_data = None

    mock_ctx = MagicMock()
    mock_ctx.session.id = "test_attachment_sess"
    mock_ctx.user_content.parts = [mock_part]
    mock_ctx.session.events = []
    mock_ctx.list_artifacts = AsyncMock(return_value=[])
    
    # 1. Test analyze_midi_file with attachment
    res = asyncio.run(analyze_midi_file(tool_context=mock_ctx))
    data = json.loads(res)
    assert data["status"] == "success"
    assert data["track_count"] == 1
    assert data["note_count"] == 256
    
    # 2. Test detect_key with attachment
    res_key = asyncio.run(detect_key(tool_context=mock_ctx))
    data_key = json.loads(res_key)
    assert data_key["status"] == "success"
    assert "detected_key" in data_key
    
    # 3. Test import_midi_to_score with attachment
    res_import = asyncio.run(import_midi_to_score(tool_context=mock_ctx))
    data_import = json.loads(res_import)
    assert data_import["status"] == "success"
    
    # 4. Test missing attachment error
    mock_ctx_empty = MagicMock()
    mock_ctx_empty.session.id = "test_empty_sess"
    mock_ctx_empty.user_content = None
    mock_ctx_empty.session.events = []
    mock_ctx_empty.list_artifacts = AsyncMock(return_value=[])
    
    res_err = asyncio.run(analyze_midi_file(tool_context=mock_ctx_empty))
    data_err = json.loads(res_err)
    assert data_err["status"] == "error"
    
    # Clean up the generated asset files
    uploaded_midi_file = PROJECT_ROOT / "skills" / "midi_analytics" / "assets" / "uploaded_test_attachment_sess.mid"
    if uploaded_midi_file.is_file():
        uploaded_midi_file.unlink()
        
    score_json = PROJECT_ROOT / "skills" / "score_construction" / "assets" / "score_test_attachment_sess.json"
    if score_json.is_file():
        score_json.unlink()
        
    uploaded_key_file = PROJECT_ROOT / "skills" / "music_theory_query" / "assets" / "uploaded_test_attachment_sess.mid"
    if uploaded_key_file.is_file():
        uploaded_key_file.unlink()


def test_instrument_management():
    from agents.music_assistant.agent import list_soundfonts, list_soundfont_instruments, assign_instrument_to_track
    from unittest.mock import MagicMock
    
    # 1. Test list_soundfonts
    sf_res = list_soundfonts()
    sf_data = json.loads(sf_res)
    assert sf_data["status"] == "success"
    assert len(sf_data["soundfonts"]) == 2
    
    # 2. Test list_soundfont_instruments
    inst_res = list_soundfont_instruments()
    inst_data = json.loads(inst_res)
    assert inst_data["status"] == "success"
    assert "Piano" in inst_data["instrument_categories"]
    assert inst_data["instrument_categories"]["Piano"]["0"] == "Acoustic Grand Piano"
    
    # 3. Test assign_instrument_to_track
    session_id = "test_assign_sess"
    # First initialize a score so we can modify it
    state_file = PROJECT_ROOT / "skills" / "score_construction" / "assets" / f"score_{session_id}.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    
    initial_state = {
        "time_signature": "4/4",
        "key_signature": "C Major",
        "parts": [
            {
                "id": "melody",
                "name": "Melody",
                "clef": "treble",
                "measures": []
            }
        ]
    }
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(initial_state, f)
        
    try:
        mock_ctx = MagicMock()
        mock_ctx.session.id = session_id
        
        # Assign a new instrument program
        assign_res = assign_instrument_to_track(mock_ctx, part_id="melody", program=65, is_percussion=True)
        assign_data = json.loads(assign_res)
        assert assign_data["status"] == "success"
        assert assign_data["part_id"] == "melody"
        assert assign_data["program"] == 65
        assert assign_data["is_percussion"] is True
        
        # Verify JSON file has been updated
        with open(state_file, "r") as f:
            updated_state = json.load(f)
        assert updated_state["parts"][0]["program"] == 65
        assert updated_state["parts"][0]["is_percussion"] is True
        
    finally:
        state_file.unlink(missing_ok=True)


def test_tempo_and_track_filtering():
    from agents.music_assistant.agent import set_score_tempo, synthesize_score
    from unittest.mock import MagicMock, AsyncMock
    import asyncio
    
    session_id = "test_tempo_track_sess"
    state_file = PROJECT_ROOT / "skills" / "score_construction" / "assets" / f"score_{session_id}.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize a score with two tracks/parts
    initial_state = {
        "time_signature": "4/4",
        "key_signature": "C Major",
        "tempos": [{"offset": 0.0, "bpm": 120.0}],
        "parts": [
            {
                "id": "melody",
                "name": "Melody Part",
                "clef": "treble",
                "program": 0,
                "measures": [
                    {
                        "number": 1,
                        "events": [
                            {"pitches": ["C4"], "duration": "quarter"},
                            {"pitches": ["D4"], "duration": "quarter"}
                        ]
                    }
                ]
            },
            {
                "id": "harmony",
                "name": "Harmony Part",
                "clef": "treble",
                "program": 48, # Strings
                "measures": [
                    {
                        "number": 1,
                        "events": [
                            {"pitches": ["E4"], "duration": "quarter"},
                            {"pitches": ["G4"], "duration": "quarter"}
                        ]
                    }
                ]
            }
        ]
    }
    
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(initial_state, f)
        
    try:
        mock_ctx = MagicMock()
        mock_ctx.session.id = session_id
        mock_ctx.save_artifact = AsyncMock()
        
        # 1. Test set_score_tempo
        tempo_res = set_score_tempo(mock_ctx, bpm=140.0, offset=4.0)
        tempo_data = json.loads(tempo_res)
        assert tempo_data["status"] == "success"
        assert tempo_data["bpm"] == 140.0
        assert tempo_data["offset"] == 4.0
        
        # Verify tempos updated in JSON file
        with open(state_file, "r") as f:
            updated_state = json.load(f)
        assert len(updated_state["tempos"]) == 2
        assert updated_state["tempos"][1]["bpm"] == 140.0
        
        # 2. Test synthesize_score with track filtering (selecting only melody part)
        synth_res = asyncio.run(synthesize_score(mock_ctx, tracks="melody"))
        synth_data = json.loads(synth_res)
        assert synth_data["status"] == "success"
        
        # Clean up generated wav file
        wav_path = PROJECT_ROOT / "skills" / "acoustic_audio_synthesis" / "assets" / f"score_{session_id}.wav"
        if wav_path.is_file():
            wav_path.unlink()
            
    finally:
        state_file.unlink(missing_ok=True)


def test_score_manager_add_abc():
    from agents.music_assistant.agent import add_abc_to_score
    from unittest.mock import MagicMock
    
    session_id = "test_abc_unit_sess"
    
    # 1. Init score
    res = run_script("skills/score_construction/scripts/score_manager.py", ["init", "--time-signature", "4/4", "--key-signature", "C Major", "--session-id", session_id])
    assert res.returncode == 0
    
    try:
        # 2. Add notes via ABC notation subcommand directly
        res = run_script("skills/score_construction/scripts/score_manager.py", [
            "add-abc",
            "--abc", "C D E F",
            "--session-id", session_id
        ])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert data["status"] == "success"
        assert data["added_events_count"] == 4
        
        # Verify JSON content
        state_file = PROJECT_ROOT / "skills" / "score_construction" / "assets" / f"score_{session_id}.json"
        assert state_file.is_file()
        with open(state_file, "r") as f:
            state = json.load(f)
        events = state["parts"][0]["measures"][0]["events"]
        assert len(events) == 4
        assert events[0]["pitches"] == ["C4"]
        assert events[3]["pitches"] == ["F4"]
        
        # 3. Add notes via TinyNotation using agent tool wrapper
        mock_ctx = MagicMock()
        mock_ctx.session.id = session_id
        
        # Use TinyNotation to add G A B c
        tool_res = add_abc_to_score(mock_ctx, abc="tinyNotation: G A B c")
        tool_data = json.loads(tool_res)
        assert tool_data["status"] == "success"
        assert tool_data["added_events_count"] == 4
        
        # Verify that measure 2 was created (since G A B c overflows measure 1)
        with open(state_file, "r") as f:
            state = json.load(f)
        measures = state["parts"][0]["measures"]
        assert len(measures) == 2
        assert measures[1]["number"] == 2
        assert measures[1]["events"][0]["pitches"] == ["G3"]  # TinyNotation G defaults to G3
        
    finally:
        state_file = PROJECT_ROOT / "skills" / "score_construction" / "assets" / f"score_{session_id}.json"
        state_file.unlink(missing_ok=True)





