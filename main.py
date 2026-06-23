import os
import sys
import warnings
from pathlib import Path

# Suppress the experimental JSON schema warning from google.adk tools
warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")

# Add the 'agents' directory to the path so the agent package can be imported directly
AGENTS_DIR = Path(__file__).parent / "agents"
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

# Import ADK runners and in-memory services for local execution
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService

# Import the configured ADK App from the music_assistant agent
from music_assistant.agent import app

from google.genai import types

def run_agent_locally(user_input: str):
    """
    Executes the single-agent Root container locally using the ADK Runner.
    """
    # Initialize the Runner with in-memory persistence providers and auto-session creation
    runner = Runner(
        app=app,
        session_service=InMemorySessionService(),
        artifact_service=InMemoryArtifactService(),
        auto_create_session=True,
    )
    
    # Run a single invocation turn
    session_id = "local-music-session"
    user_id = "local-user"
    print(f"Sending input: '{user_input}' to agent: '{app.name}'...\n")
    
    # Construct the input message format expected by google-adk v2.0
    new_message = types.Content(
        role="user",
        parts=[types.Part(text=user_input)]
    )
    
    response_stream = runner.run(
        user_id=user_id,
        session_id=session_id,
        new_message=new_message
    )
    
    print("--- Agent Response ---")
    for event in response_stream:
        if event.message and event.message.parts:
            for part in event.message.parts:
                if part.text:
                    print(part.text, end="", flush=True)
    print("\n----------------------")

if __name__ == "__main__":
    # Example execution query
    run_agent_locally("What is the interval in semitones and name between C4 and G4?")


