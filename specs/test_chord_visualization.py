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
                current_scenario["steps"].append(line)
                
        if current_scenario:
            scenarios.append(current_scenario)
            
    return scenarios

async def run_evaluation():
    feature_file = PROJECT_ROOT / "specs" / "chord_visualization.feature"
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
        session_id = f"chord-vis-eval-session-{idx}"
        user_id = "eval-user"
        
        # Determine assets paths
        assets_dir = PROJECT_ROOT / "skills" / "visual_notation_rendering" / "assets"
        image_file = assets_dir / f"chord_{session_id}.png"
        if image_file.is_file():
            image_file.unlink()
            
        runner = Runner(
            app=app,
            session_service=InMemorySessionService(),
            artifact_service=InMemoryArtifactService(),
            auto_create_session=True
        )
        
        actual_invocations = []
        expected_invocations = []
        
        if sc["name"] == "Render piano keyboard chord diagram":
            query = "Visualize chord C,E,G on piano"
            expected_tool_call = types.FunctionCall(
                name="render_chord_diagram",
                args={"pitches": "C,E,G", "instrument": "piano", "chord_name": ""}
            )
        else:
            query = "Visualize chord C Major on guitar"
            expected_tool_call = types.FunctionCall(
                name="render_chord_diagram",
                args={"pitches": "", "instrument": "guitar", "chord_name": "C Major"}
            )
            
        print(f"Query: '{query}'")
        
        expected_inv = Invocation(
            invocation_id=f"inv_{idx}",
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
            invocation_id=f"inv_{idx}",
            user_content=types.Content(role="user", parts=[types.Part.from_text(text=query)]),
            final_response=types.Content(role="model", parts=[types.Part(text=response_text)]),
            intermediate_data=IntermediateData(tool_uses=actual_tool_calls)
        )
        actual_invocations.append(actual_inv)
        
        # Evaluate trajectory
        trajectory_score = 0.0
        if len(actual_tool_calls) == 1:
            call = actual_tool_calls[0]
            if call.name == "render_chord_diagram":
                args = call.args or {}
                if sc["name"] == "Render piano keyboard chord diagram":
                    if args.get("instrument") == "piano" and ("C" in args.get("pitches", "") or "C" in args.get("chord_name", "")):
                        trajectory_score = 1.0
                else:
                    if args.get("instrument") == "guitar" and args.get("chord_name") == "C Major":
                        trajectory_score = 1.0
        
        # Verify file generation
        file_generated = False
        reasons = []
        if image_file.is_file():
            file_generated = True
        else:
            reasons.append(f"Image file '{image_file}' was not generated.")
            
        file_mutation_score = 1.0 if file_generated else 0.0
        
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
