import os
import sys
import re
import json
import asyncio
import warnings
from pathlib import Path

# Suppress the experimental JSON schema warning from google.adk tools
warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")

# Add project root and agents directory to path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "agents"))

# Import ADK elements
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.adk.evaluation.eval_case import Invocation, IntermediateData
from google.adk.evaluation.eval_metrics import EvalMetric, ToolTrajectoryCriterion
from google.adk.evaluation.trajectory_evaluator import TrajectoryEvaluator
from google.genai import types

# Import agent app
from music_assistant.agent import app

def parse_gherkin_scenarios(feature_file_path: str):
    scenarios = []
    current_scenario = None
    
    with open(feature_file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("@"):
                continue
            
            if line.startswith("Scenario:"):
                if current_scenario:
                    scenarios.append(current_scenario)
                current_scenario = {
                    "name": line[9:].strip(),
                    "steps": []
                }
            elif current_scenario:
                # Add steps to the current scenario
                current_scenario["steps"].append(line)
                
        if current_scenario:
            scenarios.append(current_scenario)
            
    return scenarios

async def run_evaluation():
    feature_file = PROJECT_ROOT / "specs" / "score_editing.feature"
    print(f"Reading Gherkin scenarios from: {feature_file}\n")
    scenarios = parse_gherkin_scenarios(str(feature_file))
    
    criterion = ToolTrajectoryCriterion(
        threshold=1.0,
        match_type=ToolTrajectoryCriterion.MatchType.IN_ORDER
    )
    eval_metric = EvalMetric(
        metric_name="trajectory_accuracy",
        criterion=criterion
    )
    evaluator = TrajectoryEvaluator(eval_metric=eval_metric)
    
    scoring_blocks = []
    
    for idx, sc in enumerate(scenarios):
        print(f"==================================================")
        print(f"Running Scenario {idx+1}: {sc['name']}")
        print(f"==================================================")
        session_id = f"score-edit-eval-session-{idx}"
        user_id = "eval-user"
        state_file = PROJECT_ROOT / "skills" / "score_construction" / "assets" / f"score_{session_id}.json"

        # Given a clean score state
        if state_file.is_file():
            state_file.unlink()
        print("Cleaned score state file (Given a clean score state)")
        
        # Initialize Runner
        runner = Runner(
            app=app,
            session_service=InMemorySessionService(),
            artifact_service=InMemoryArtifactService(),
            auto_create_session=True
        )
        
        actual_invocations = []
        expected_invocations = []
        turn_counter = 1
        
        # We will parse steps and execute queries
        # Some steps are Given, When (which trigger actions), and Then (which check state/actions)
        for step in sc["steps"]:
            # Action: Initialize score
            match_init = re.search(r'initialize a blank score with time signature "([^"]+)"', step)
            if match_init:
                ts = match_init.group(1)
                query = f"Initialize a blank score with time signature {ts}"
                print(f"\nTurn {turn_counter} Query: '{query}'")
                
                expected_tool_call = types.FunctionCall(
                    name="initialize_score",
                    args={"time_signature": ts}
                )
                expected_inv = Invocation(
                    invocation_id=f"inv_{idx}_t{turn_counter}",
                    user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
                    final_response=None,
                    intermediate_data=IntermediateData(tool_uses=[expected_tool_call])
                )
                expected_invocations.append(expected_inv)
                
                response_stream = runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=types.Content(role="user", parts=[types.Part.from_text(text=query)])
                )
                
                actual_tool_calls = []
                response_text = ""
                async for event in response_stream:
                    if hasattr(event, "message") and event.message and event.message.parts:
                        for part in event.message.parts:
                            if part.text:
                                response_text += part.text
                            if part.function_call:
                                actual_tool_calls.append(part.function_call)
                
                print(f"Raw Agent Response: {response_text.strip()}")
                print(f"Actual Tool Calls: {actual_tool_calls}")
                
                actual_inv = Invocation(
                    invocation_id=f"inv_{idx}_t{turn_counter}",
                    user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
                    final_response=types.Content(role="model", parts=[types.Part(text=response_text)]),
                    intermediate_data=IntermediateData(tool_uses=actual_tool_calls)
                )
                actual_invocations.append(actual_inv)
                turn_counter += 1
                continue
                
            # Action: Add note
            # e.g., When the user requests to add note "C4" with duration "quarter" to part "melody"
            # or add note "C4" with duration "quarter"
            match_add = re.search(r'add note "([^"]+)" with duration "([^"]+)"(?: to part "([^"]+)")?', step)
            if match_add:
                pitch = match_add.group(1)
                duration = match_add.group(2)
                part_id = match_add.group(3) or "melody"
                query = f"Add note {pitch} with duration {duration} to part {part_id}"
                print(f"\nTurn {turn_counter} Query: '{query}'")
                
                expected_tool_call = types.FunctionCall(
                    name="add_note_to_score",
                    args={"pitch": pitch, "duration": duration, "part_id": part_id}
                )
                expected_inv = Invocation(
                    invocation_id=f"inv_{idx}_t{turn_counter}",
                    user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
                    final_response=None,
                    intermediate_data=IntermediateData(tool_uses=[expected_tool_call])
                )
                expected_invocations.append(expected_inv)
                
                response_stream = runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=types.Content(role="user", parts=[types.Part.from_text(text=query)])
                )
                
                actual_tool_calls = []
                response_text = ""
                async for event in response_stream:
                    if hasattr(event, "message") and event.message and event.message.parts:
                        for part in event.message.parts:
                            if part.text:
                                response_text += part.text
                            if part.function_call:
                                actual_tool_calls.append(part.function_call)
                
                print(f"Raw Agent Response: {response_text.strip()}")
                print(f"Actual Tool Calls: {actual_tool_calls}")
                
                actual_inv = Invocation(
                    invocation_id=f"inv_{idx}_t{turn_counter}",
                    user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
                    final_response=types.Content(role="model", parts=[types.Part(text=response_text)]),
                    intermediate_data=IntermediateData(tool_uses=actual_tool_calls)
                )
                actual_invocations.append(actual_inv)
                turn_counter += 1
                continue
                
            # Action: Delete note
            match_del_note = re.search(r'delete the note at measure (\d+) index (\d+)', step)
            if match_del_note:
                m_num = int(match_del_note.group(1))
                idx_num = int(match_del_note.group(2))
                query = f"Delete the note in part melody at measure {m_num} index {idx_num}"
                print(f"\nTurn {turn_counter} Query: '{query}'")
                
                expected_tool_call = types.FunctionCall(
                    name="delete_note_from_score",
                    args={"measure": m_num, "event_index": idx_num, "part_id": "melody"}
                )
                expected_inv = Invocation(
                    invocation_id=f"inv_{idx}_t{turn_counter}",
                    user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
                    final_response=None,
                    intermediate_data=IntermediateData(tool_uses=[expected_tool_call])
                )
                expected_invocations.append(expected_inv)
                
                response_stream = runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=types.Content(role="user", parts=[types.Part.from_text(text=query)])
                )
                
                actual_tool_calls = []
                response_text = ""
                async for event in response_stream:
                    if hasattr(event, "message") and event.message and event.message.parts:
                        for part in event.message.parts:
                            if part.text:
                                response_text += part.text
                            if part.function_call:
                                actual_tool_calls.append(part.function_call)
                
                print(f"Raw Agent Response: {response_text.strip()}")
                print(f"Actual Tool Calls: {actual_tool_calls}")
                
                actual_inv = Invocation(
                    invocation_id=f"inv_{idx}_t{turn_counter}",
                    user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
                    final_response=types.Content(role="model", parts=[types.Part(text=response_text)]),
                    intermediate_data=IntermediateData(tool_uses=actual_tool_calls)
                )
                actual_invocations.append(actual_inv)
                turn_counter += 1
                continue
                
            # Action: Edit note
            match_edit_note = re.search(r'edit the note at measure (\d+) index (\d+) to pitch "([^"]+)" and duration "([^"]+)"', step)
            if match_edit_note:
                m_num = int(match_edit_note.group(1))
                idx_num = int(match_edit_note.group(2))
                pitch = match_edit_note.group(3)
                duration = match_edit_note.group(4)
                query = f"Edit the note in part melody at measure {m_num} index {idx_num} to pitch {pitch} and duration {duration}"
                print(f"\nTurn {turn_counter} Query: '{query}'")
                
                expected_tool_call = types.FunctionCall(
                    name="edit_note_in_score",
                    args={"measure": m_num, "event_index": idx_num, "pitch": pitch, "duration": duration, "part_id": "melody"}
                )
                expected_inv = Invocation(
                    invocation_id=f"inv_{idx}_t{turn_counter}",
                    user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
                    final_response=None,
                    intermediate_data=IntermediateData(tool_uses=[expected_tool_call])
                )
                expected_invocations.append(expected_inv)
                
                response_stream = runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=types.Content(role="user", parts=[types.Part.from_text(text=query)])
                )
                
                actual_tool_calls = []
                response_text = ""
                async for event in response_stream:
                    if hasattr(event, "message") and event.message and event.message.parts:
                        for part in event.message.parts:
                            if part.text:
                                response_text += part.text
                            if part.function_call:
                                actual_tool_calls.append(part.function_call)
                
                print(f"Raw Agent Response: {response_text.strip()}")
                print(f"Actual Tool Calls: {actual_tool_calls}")
                
                actual_inv = Invocation(
                    invocation_id=f"inv_{idx}_t{turn_counter}",
                    user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
                    final_response=types.Content(role="model", parts=[types.Part(text=response_text)]),
                    intermediate_data=IntermediateData(tool_uses=actual_tool_calls)
                )
                actual_invocations.append(actual_inv)
                turn_counter += 1
                continue
                
            # Action: Insert measure
            match_ins_meas = re.search(r'insert a measure at measure index (\d+)', step)
            if match_ins_meas:
                m_num = int(match_ins_meas.group(1))
                query = f"Insert a measure at index {m_num}"
                print(f"\nTurn {turn_counter} Query: '{query}'")
                
                expected_tool_call = types.FunctionCall(
                    name="insert_measure_into_score",
                    args={"at": m_num}
                )
                expected_inv = Invocation(
                    invocation_id=f"inv_{idx}_t{turn_counter}",
                    user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
                    final_response=None,
                    intermediate_data=IntermediateData(tool_uses=[expected_tool_call])
                )
                expected_invocations.append(expected_inv)
                
                response_stream = runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=types.Content(role="user", parts=[types.Part.from_text(text=query)])
                )
                
                actual_tool_calls = []
                response_text = ""
                async for event in response_stream:
                    if hasattr(event, "message") and event.message and event.message.parts:
                        for part in event.message.parts:
                            if part.text:
                                response_text += part.text
                            if part.function_call:
                                actual_tool_calls.append(part.function_call)
                
                print(f"Raw Agent Response: {response_text.strip()}")
                print(f"Actual Tool Calls: {actual_tool_calls}")
                
                actual_inv = Invocation(
                    invocation_id=f"inv_{idx}_t{turn_counter}",
                    user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
                    final_response=types.Content(role="model", parts=[types.Part(text=response_text)]),
                    intermediate_data=IntermediateData(tool_uses=actual_tool_calls)
                )
                actual_invocations.append(actual_inv)
                turn_counter += 1
                continue
                
            # Action: Delete measure
            match_del_meas = re.search(r'delete measure (\d+)', step)
            if match_del_meas:
                m_num = int(match_del_meas.group(1))
                query = f"Delete measure {m_num}"
                print(f"\nTurn {turn_counter} Query: '{query}'")
                
                expected_tool_call = types.FunctionCall(
                    name="delete_measure_from_score",
                    args={"measure": m_num}
                )
                expected_inv = Invocation(
                    invocation_id=f"inv_{idx}_t{turn_counter}",
                    user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
                    final_response=None,
                    intermediate_data=IntermediateData(tool_uses=[expected_tool_call])
                )
                expected_invocations.append(expected_inv)
                
                response_stream = runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=types.Content(role="user", parts=[types.Part.from_text(text=query)])
                )
                
                actual_tool_calls = []
                response_text = ""
                async for event in response_stream:
                    if hasattr(event, "message") and event.message and event.message.parts:
                        for part in event.message.parts:
                            if part.text:
                                response_text += part.text
                            if part.function_call:
                                actual_tool_calls.append(part.function_call)
                
                print(f"Raw Agent Response: {response_text.strip()}")
                print(f"Actual Tool Calls: {actual_tool_calls}")
                
                actual_inv = Invocation(
                    invocation_id=f"inv_{idx}_t{turn_counter}",
                    user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
                    final_response=types.Content(role="model", parts=[types.Part(text=response_text)]),
                    intermediate_data=IntermediateData(tool_uses=actual_tool_calls)
                )
                actual_invocations.append(actual_inv)
                turn_counter += 1
                continue
                
            # Action: Transpose single part
            match_trans_part = re.search(r'transpose part "([^"]+)" by (\d+) semitones', step)
            if match_trans_part:
                part_id = match_trans_part.group(1)
                semi = int(match_trans_part.group(2))
                query = f"Transpose part {part_id} by {semi} semitones"
                print(f"\nTurn {turn_counter} Query: '{query}'")
                
                expected_tool_call = types.FunctionCall(
                    name="transpose_part_in_score",
                    args={"part_id": part_id, "semitones": semi}
                )
                expected_inv = Invocation(
                    invocation_id=f"inv_{idx}_t{turn_counter}",
                    user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
                    final_response=None,
                    intermediate_data=IntermediateData(tool_uses=[expected_tool_call])
                )
                expected_invocations.append(expected_inv)
                
                response_stream = runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=types.Content(role="user", parts=[types.Part.from_text(text=query)])
                )
                
                actual_tool_calls = []
                response_text = ""
                async for event in response_stream:
                    if hasattr(event, "message") and event.message and event.message.parts:
                        for part in event.message.parts:
                            if part.text:
                                response_text += part.text
                            if part.function_call:
                                actual_tool_calls.append(part.function_call)
                
                print(f"Raw Agent Response: {response_text.strip()}")
                print(f"Actual Tool Calls: {actual_tool_calls}")
                
                actual_inv = Invocation(
                    invocation_id=f"inv_{idx}_t{turn_counter}",
                    user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
                    final_response=types.Content(role="model", parts=[types.Part(text=response_text)]),
                    intermediate_data=IntermediateData(tool_uses=actual_tool_calls)
                )
                actual_invocations.append(actual_inv)
                turn_counter += 1
                continue

        # Evaluate trajectory accuracy
        eval_result = evaluator.evaluate_invocations(
            actual_invocations=actual_invocations,
            expected_invocations=expected_invocations
        )
        trajectory_score = eval_result.overall_score
        
        # Verify JSON file mutations based on scenario name
        file_mutated = False
        reasons = []
        if state_file.is_file():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                
                if sc["name"] == "Delete a note and replace with a rest":
                    # Assert first event of first measure of melody part is rest of quarter duration
                    part = next(p for p in state["parts"] if p["id"] == "melody")
                    event = part["measures"][0]["events"][0]
                    if event["pitches"] == ["rest"] and event["duration"] == "quarter":
                        file_mutated = True
                    else:
                        reasons.append(f"Event is {event}, expected rest of duration quarter")
                        
                elif sc["name"] == "Edit a note pitch and duration":
                    # Assert event at measure 1 index 0 is pitch "E4" and duration "half"
                    part = next(p for p in state["parts"] if p["id"] == "melody")
                    event = part["measures"][0]["events"][0]
                    if event["pitches"] == ["E4"] and event["duration"] == "half":
                        file_mutated = True
                    else:
                        reasons.append(f"Event is {event}, expected E4 of duration half")
                        
                elif sc["name"] == "Insert and delete a measure":
                    # After insert and delete, measure 1 should contain note C4
                    part = next(p for p in state["parts"] if p["id"] == "melody")
                    # Let's find measure 1
                    m1 = next((m for m in part["measures"] if m["number"] == 1), None)
                    if m1 and m1["events"] and m1["events"][0]["pitches"] == ["C4"]:
                        file_mutated = True
                    else:
                        reasons.append(f"Measure 1 does not contain C4: {m1}")
                        
                elif sc["name"] == "Transpose a single part":
                    # melody part note is pitch "C4", bassline part note is pitch "D3"
                    melody_part = next(p for p in state["parts"] if p["id"] == "melody")
                    bass_part = next(p for p in state["parts"] if p["id"] == "bassline")
                    mel_note = melody_part["measures"][0]["events"][0]["pitches"][0]
                    bass_note = bass_part["measures"][0]["events"][0]["pitches"][0]
                    if mel_note == "C4" and bass_note == "D3":
                        file_mutated = True
                    else:
                        reasons.append(f"Melody note: {mel_note} (expected C4), Bass note: {bass_note} (expected D3)")
                else:
                    reasons.append(f"Unknown scenario validation: {sc['name']}")
                    
            except Exception as e:
                reasons.append(f"Failed to read/parse state file: {e}")
        else:
            reasons.append("State file does not exist after execution")
            
        file_mutation_score = 1.0 if file_mutated else 0.0
        
        scoring_blocks.append({
            "scenario": sc["name"],
            "trajectory_score": trajectory_score,
            "file_mutation_score": file_mutation_score,
            "reasons": reasons
        })
        
    print(f"\n==================================================")
    print(f"FINAL VALIDATION SCORING BLOCKS")
    print(f"==================================================")
    for block in scoring_blocks:
        print(f"Scenario: {block['scenario']}")
        print(f"  Trajectory Validation (IN_ORDER): {block['trajectory_score'] * 100}%")
        print(f"  File Mutation State Validation:   {block['file_mutation_score'] * 100}%")
        if block["reasons"]:
            print(f"  Fail Reasons: {block['reasons']}")
        print()

if __name__ == "__main__":
    asyncio.run(run_evaluation())
