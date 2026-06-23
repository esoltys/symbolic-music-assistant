from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

def analyze_dummy(query: str) -> str:
    """A placeholder analysis tool to verify the agent's scaffolding.

    Args:
        query: The user query to parse or analyze.

    Returns:
        A string confirmation of the analysis.
    """
    return f"Verified: Scaffolding dummy analysis for '{query}'"

root_agent = Agent(
    name="music_assistant_root",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="You are a symbolic music assistant designed to help with music theory, chords, scores, and MIDI files.",
    tools=[analyze_dummy],
)

app = App(
    root_agent=root_agent,
    name="music_assistant",
)
