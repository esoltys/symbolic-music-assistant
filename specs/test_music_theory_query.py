import os
import sys
import re
import json
import asyncio
from pathlib import Path

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
            if not line:
                continue
            
            if line.startswith("Scenario:"):
                if current_scenario:
                    scenarios.append(current_scenario)
                current_scenario = {
                    "name": line[9:].strip(),
                    "start_note": None,
                    "end_note": None,
                    "expected_semitones": None,
                    "expected_interval_name": None,
                    "expected_status": None,
                    "expected_error": None
                }
            elif current_scenario:
                # Given the start note is "C4"
                match_start = re.search(r'start note is "([^"]+)"', line)
                if match_start:
                    current_scenario["start_note"] = match_start.group(1)
                
                # And the end note is "G4"
                match_end = re.search(r'end note is "([^"]+)"', line)
                if match_end:
                    current_scenario["end_note"] = match_end.group(1)
                
                # Then the calculation should succeed
                if "calculation should succeed" in line:
                    current_scenario["expected_status"] = "success"
                
                # Then the calculation should fail
                if "calculation should fail" in line:
                    current_scenario["expected_status"] = "fail"
                
                # And the result should be 7 semitones
                match_semi = re.search(r'result should be (\d+) semitones', line)
                if match_semi:
                    current_scenario["expected_semitones"] = int(match_semi.group(1))
                
                # And the interval name should be "Perfect 5th"
                match_name = re.search(r'interval name should be "([^"]+)"', line)
                if match_name:
                    current_scenario["expected_interval_name"] = match_name.group(1)
                
                # And the error response should mention "Note out of valid MIDI/pitch range"
                match_err = re.search(r'error response should mention "([^"]+)"', line)
                if match_err:
                    current_scenario["expected_error"] = match_err.group(1)
                    
        if current_scenario:
            scenarios.append(current_scenario)
            
    return scenarios

async def run_evaluation():
    feature_file = PROJECT_ROOT / "specs" / "music_theory_query.feature"
    print(f"Reading Gherkin scenarios from: {feature_file}\n")
    scenarios = parse_gherkin_scenarios(str(feature_file))
    
    # Initialize Runner
    runner = Runner(
        app=app,
        session_service=InMemorySessionService(),
        artifact_service=InMemoryArtifactService(),
        auto_create_session=True
    )
    
    # Setup TrajectoryEvaluator with ANY_ORDER
    criterion = ToolTrajectoryCriterion(
        threshold=1.0,
        match_type=ToolTrajectoryCriterion.MatchType.ANY_ORDER
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
        
        query = f"What is the interval in semitones and name between {sc['start_note']} and {sc['end_note']}?"
        print(f"Query: '{query}'")
        
        # Define expected tool call
        expected_tool_call = types.FunctionCall(
            name="evaluate_interval",
            args={"start_note": sc["start_note"], "end_note": sc["end_note"]}
        )
        
        expected_invocation = Invocation(
            invocation_id=f"inv_{idx}",
            user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
            final_response=None,
            intermediate_data=IntermediateData(
                tool_uses=[expected_tool_call]
            )
        )
        
        # Run agent
        session_id = f"eval-session-{idx}"
        new_message = types.Content(
            role="user",
            parts=[types.Part(text=query)]
        )
        
        # Run natively using async generator
        response_stream = runner.run_async(
            user_id="eval-user",
            session_id=session_id,
            new_message=new_message
        )
        
        actual_tool_calls = []
        response_text = ""
        
        # Process response stream
        async for event in response_stream:
            if hasattr(event, "message") and event.message and event.message.parts:
                for part in event.message.parts:
                    if part.text:
                        response_text += part.text
                    if part.function_call:
                        actual_tool_calls.append(part.function_call)
                        
        print(f"\nRaw Agent Response:\n{response_text.strip()}\n")
        print(f"Actual Tool Calls: {actual_tool_calls}")
        
        actual_invocation = Invocation(
            invocation_id=f"inv_{idx}",
            user_content=new_message,
            final_response=types.Content(role="model", parts=[types.Part(text=response_text)]),
            intermediate_data=IntermediateData(
                tool_uses=actual_tool_calls
            )
        )
        
        # Evaluate trajectory
        eval_result = evaluator.evaluate_invocations(
            actual_invocations=[actual_invocation],
            expected_invocations=[expected_invocation]
        )
        trajectory_score = eval_result.overall_score
        
        # Evaluate response text assertions
        response_passed = True
        reasons = []
        
        if sc["expected_status"] == "success":
            # Verify expected semitones (e.g. 7)
            if str(sc["expected_semitones"]) not in response_text:
                response_passed = False
                reasons.append(f"Expected semitones '{sc['expected_semitones']}' not in response")
            # Verify expected interval name (e.g. "Perfect 5th")
            if sc["expected_interval_name"] not in response_text:
                response_passed = False
                reasons.append(f"Expected interval name '{sc['expected_interval_name']}' not in response")
        else:
            # Verify expected error message (flexible matching for LLM rephrasing)
            expected_keywords = ["out of", "midi/pitch range"]
            for kw in expected_keywords:
                if kw not in response_text.lower():
                    response_passed = False
                    reasons.append(f"Expected keyword '{kw}' not in response")
                
        response_score = 1.0 if response_passed else 0.0
        
        scoring_blocks.append({
            "scenario": sc["name"],
            "trajectory_score": trajectory_score,
            "response_score": response_score,
            "reasons": reasons
        })
        
    print(f"\n==================================================")
    print(f"FINAL VALIDATION SCORING BLOCKS")
    print(f"==================================================")
    for block in scoring_blocks:
        print(f"Scenario: {block['scenario']}")
        print(f"  Trajectory Validation (ANY_ORDER): {block['trajectory_score'] * 100}%")
        print(f"  Response Assertion Validation:    {block['response_score'] * 100}%")
        if block["reasons"]:
            print(f"  Fail Reasons: {block['reasons']}")
        print()

if __name__ == "__main__":
    asyncio.run(run_evaluation())
