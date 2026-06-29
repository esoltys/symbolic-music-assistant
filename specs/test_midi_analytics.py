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
            if not line:
                continue
            
            if line.startswith("Scenario:"):
                if current_scenario:
                    scenarios.append(current_scenario)
                current_scenario = {
                    "name": line[9:].strip(),
                    "file_path": None,
                    "expected_note_count": None,
                    "expected_tempo": None
                }
            elif current_scenario:
                # Given a valid MIDI file path "skills/midi_analytics/assets/sample.mid"
                match_path = re.search(r'valid MIDI file path "([^"]+)"', line)
                if match_path:
                    current_scenario["file_path"] = match_path.group(1)
                
                # And the response should contain the note count 256
                match_notes = re.search(r'response should contain the note count (\d+)', line)
                if match_notes:
                    current_scenario["expected_note_count"] = int(match_notes.group(1))
                
                # And the response should contain the tempo 120
                match_tempo = re.search(r'response should contain the tempo (\d+)', line)
                if match_tempo:
                    current_scenario["expected_tempo"] = int(match_tempo.group(1))
                    
        if current_scenario:
            scenarios.append(current_scenario)
            
    return scenarios

async def run_evaluation():
    feature_file = PROJECT_ROOT / "specs" / "midi_analytics.feature"
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
        
        query = "Analyze the attached MIDI file to extract its metrics summary."
        print(f"Query: '{query}'")
        
        # Read the file and base64-encode it
        midi_bytes = (PROJECT_ROOT / sc["file_path"]).read_bytes()
        import base64
        midi_b64 = base64.b64encode(midi_bytes).decode("utf-8")
        
        expected_attachment = {
            "fileName": Path(sc["file_path"]).name,
            "mimeType": "audio/midi",
            "base64Data": midi_b64
        }
        
        # Define expected tool call
        expected_tool_call = types.FunctionCall(
            name="analyze_midi_file",
            args={}
        )
        
        expected_invocation = Invocation(
            invocation_id=f"inv_{idx}",
            user_content=types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=query),
                    types.Part.from_bytes(data=midi_bytes, mime_type="audio/midi")
                ]
            ),
            final_response=None,
            intermediate_data=IntermediateData(
                tool_uses=[expected_tool_call]
            )
        )
        
        # Run agent
        session_id = f"eval-session-{idx}"
        new_message = types.Content(
            role="user",
            parts=[
                types.Part(text=query),
                types.Part.from_bytes(data=midi_bytes, mime_type="audio/midi")
            ]
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
        
        if str(sc["expected_note_count"]) not in response_text:
            response_passed = False
            reasons.append(f"Expected note count '{sc['expected_note_count']}' not in response")
            
        if str(sc["expected_tempo"]) not in response_text:
            response_passed = False
            reasons.append(f"Expected tempo '{sc['expected_tempo']}' not in response")
                
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
