import os
import sys
import re
import json
import asyncio
import warnings
from pathlib import Path

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "agents"))

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.adk.evaluation.eval_case import Invocation, IntermediateData
from google.adk.evaluation.eval_metrics import EvalMetric, ToolTrajectoryCriterion
from google.adk.evaluation.trajectory_evaluator import TrajectoryEvaluator
from google.genai import types

from music_assistant.agent import app

def parse_gherkin_scenarios(feature_file_path: str):
    scenarios = []
    current_scenario = None
    
    with open(feature_file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            if line.startswith("Scenario:"):
                if current_scenario:
                    scenarios.append(current_scenario)
                current_scenario = {
                    "name": line[9:].strip(),
                    "initial_key": "C Major",
                    "notes": [],
                    "expected_key": "G Major"
                }
            elif current_scenario:
                # Given a score initialized in "C Major"
                match_init = re.search(r'score initialized in "([^"]+)"', line)
                if match_init:
                    current_scenario["initial_key"] = match_init.group(1)
                
                # And notes "G4", "B4", "D5", "F#5" added to the melody
                match_notes = re.search(r'notes "([^"]+)", "([^"]+)", "([^"]+)", "([^"]+)" added to the melody', line)
                if match_notes:
                    current_scenario["notes"] = list(match_notes.groups())
                
                # And the response should contain the detected key "G Major"
                match_expected = re.search(r'response should contain the detected key "([^"]+)"', line)
                if match_expected:
                    current_scenario["expected_key"] = match_expected.group(1)
                    
        if current_scenario:
            scenarios.append(current_scenario)
            
    return scenarios

async def run_evaluation():
    feature_file = PROJECT_ROOT / "specs" / "key_detection.feature"
    print(f"Reading Gherkin scenarios from: {feature_file}\n")
    scenarios = parse_gherkin_scenarios(str(feature_file))
    
    runner = Runner(
        app=app,
        session_service=InMemorySessionService(),
        artifact_service=InMemoryArtifactService(),
        auto_create_session=True
    )
    
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
        
        query = (
            f"Please initialize a blank score in {sc['initial_key']}, "
            f"add quarter notes {', '.join(sc['notes'])} to the melody part, "
            f"and then detect what key the score is in."
        )
        print(f"Query: '{query}'")
        
        expected_tool_uses = [
            types.FunctionCall(name="initialize_score", args={"key_signature": sc["initial_key"]}),
            types.FunctionCall(name="detect_key", args={})
        ]
        for note_pitch in sc["notes"]:
            expected_tool_uses.append(
                types.FunctionCall(name="add_note_to_score", args={"pitch": note_pitch, "duration": "quarter", "part_id": "melody"})
            )
            
        expected_invocation = Invocation(
            invocation_id=f"inv_{idx}",
            user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
            final_response=None,
            intermediate_data=IntermediateData(
                tool_uses=expected_tool_uses
            )
        )
        
        session_id = f"key-eval-session-{idx}"
        new_message = types.Content(role="user", parts=[types.Part(text=query)])
        
        response_stream = runner.run_async(
            user_id="eval-user",
            session_id=session_id,
            new_message=new_message
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
        
        eval_result = evaluator.evaluate_invocations(
            actual_invocations=[actual_invocation],
            expected_invocations=[expected_invocation]
        )
        trajectory_score = eval_result.overall_score
        
        expected_key_pattern = sc["expected_key"].lower().split()[0]
        response_success = expected_key_pattern in response_text.lower()
        
        scoring_blocks.append({
            "name": sc["name"],
            "trajectory_score": trajectory_score * 100.0,
            "response_score": 100.0 if response_success else 0.0
        })
        
    print("\n==================================================")
    print("FINAL VALIDATION SCORING BLOCKS")
    print("==================================================")
    for sb in scoring_blocks:
        print(f"Scenario: {sb['name']}")
        print(f"  Trajectory Validation (ANY_ORDER): {sb['trajectory_score']}%")
        print(f"  Response Assertion Validation:    {sb['response_score']}%")
        
if __name__ == "__main__":
    asyncio.run(run_evaluation())
