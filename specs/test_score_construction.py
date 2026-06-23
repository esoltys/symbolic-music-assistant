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
                    "time_signature": "4/4",
                    "pitch": "C4",
                    "duration": "quarter"
                }
            elif current_scenario:
                # When the user requests to initialize a blank canvas with time signature "4/4"
                match_init = re.search(r'initialize a blank canvas with time signature "([^"]+)"', line)
                if match_init:
                    current_scenario["time_signature"] = match_init.group(1)
                
                # When the user requests to add note "C4" with duration "quarter"
                match_add = re.search(r'add note "([^"]+)" with duration "([^"]+)"', line)
                if match_add:
                    current_scenario["pitch"] = match_add.group(1)
                    current_scenario["duration"] = match_add.group(2)
                    
        if current_scenario:
            scenarios.append(current_scenario)
            
    return scenarios

async def run_evaluation():
    feature_file = PROJECT_ROOT / "specs" / "score_construction.feature"
    print(f"Reading Gherkin scenarios from: {feature_file}\n")
    scenarios = parse_gherkin_scenarios(str(feature_file))
    
    # Locate state file
    state_file = PROJECT_ROOT / "skills" / "score_construction" / "assets" / "canvas_state.json"
    
    # Setup TrajectoryEvaluator with IN_ORDER
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
        
        # Given a clean canvas state: delete/clear the state file
        if state_file.is_file():
            state_file.unlink()
        print("Cleaned canvas state file (Given a clean canvas state)")
        
        # Initialize Runner
        runner = Runner(
            app=app,
            session_service=InMemorySessionService(),
            artifact_service=InMemoryArtifactService(),
            auto_create_session=True
        )
        
        session_id = f"score-eval-session-{idx}"
        user_id = "eval-user"
        
        # Turn 1: Initialize canvas
        query1 = f"Initialize a blank canvas with time signature {sc['time_signature']}"
        print(f"\nTurn 1 Query: '{query1}'")
        
        expected_tool_call1 = types.FunctionCall(
            name="initialize_canvas",
            args={"time_signature": sc["time_signature"]}
        )
        
        expected_inv1 = Invocation(
            invocation_id=f"inv_{idx}_t1",
            user_content=types.Content(role="user", parts=[types.Part.from_text(text=query1)]),
            final_response=None,
            intermediate_data=IntermediateData(
                tool_uses=[expected_tool_call1]
            )
        )
        
        response_stream1 = runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=query1)])
        )
        
        actual_tool_calls1 = []
        response_text1 = ""
        async for event in response_stream1:
            if hasattr(event, "message") and event.message and event.message.parts:
                for part in event.message.parts:
                    if part.text:
                        response_text1 += part.text
                    if part.function_call:
                        actual_tool_calls1.append(part.function_call)
                        
        print(f"Raw Agent Response: {response_text1.strip()}")
        print(f"Actual Tool Calls: {actual_tool_calls1}")
        
        actual_inv1 = Invocation(
            invocation_id=f"inv_{idx}_t1",
            user_content=types.Content(role="user", parts=[types.Part.from_text(text=query1)]),
            final_response=types.Content(role="model", parts=[types.Part(text=response_text1)]),
            intermediate_data=IntermediateData(
                tool_uses=actual_tool_calls1
            )
        )
        
        # Turn 2: Add note
        query2 = f"Add note {sc['pitch']} with duration {sc['duration']}"
        print(f"\nTurn 2 Query: '{query2}'")
        
        expected_tool_call2 = types.FunctionCall(
            name="add_note_to_canvas",
            args={"pitch": sc["pitch"], "duration": sc["duration"]}
        )
        
        expected_inv2 = Invocation(
            invocation_id=f"inv_{idx}_t2",
            user_content=types.Content(role="user", parts=[types.Part.from_text(text=query2)]),
            final_response=None,
            intermediate_data=IntermediateData(
                tool_uses=[expected_tool_call2]
            )
        )
        
        response_stream2 = runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=query2)])
        )
        
        actual_tool_calls2 = []
        response_text2 = ""
        async for event in response_stream2:
            if hasattr(event, "message") and event.message and event.message.parts:
                for part in event.message.parts:
                    if part.text:
                        response_text2 += part.text
                    if part.function_call:
                        actual_tool_calls2.append(part.function_call)
                        
        print(f"Raw Agent Response: {response_text2.strip()}")
        print(f"Actual Tool Calls: {actual_tool_calls2}")
        
        actual_inv2 = Invocation(
            invocation_id=f"inv_{idx}_t2",
            user_content=types.Content(role="user", parts=[types.Part.from_text(text=query2)]),
            final_response=types.Content(role="model", parts=[types.Part(text=response_text2)]),
            intermediate_data=IntermediateData(
                tool_uses=actual_tool_calls2
            )
        )
        
        # Evaluate trajectory (combining turns chronologically)
        eval_result = evaluator.evaluate_invocations(
            actual_invocations=[actual_inv1, actual_inv2],
            expected_invocations=[expected_inv1, expected_inv2]
        )
        trajectory_score = eval_result.overall_score
        
        # Assert file mutation correctly occurred
        file_mutated = False
        reasons = []
        if state_file.is_file():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                if state.get("time_signature") == sc["time_signature"]:
                    notes = state.get("notes", [])
                    if len(notes) == 1:
                        note = notes[0]
                        if note.get("pitch") == sc["pitch"] and note.get("duration") == sc["duration"]:
                            file_mutated = True
                        else:
                            reasons.append(f"State note {note} does not match expected pitch {sc['pitch']} and duration {sc['duration']}")
                    else:
                        reasons.append(f"Notes count in state is {len(notes)}, expected 1")
                else:
                    reasons.append(f"Time signature in state is {state.get('time_signature')}, expected {sc['time_signature']}")
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
