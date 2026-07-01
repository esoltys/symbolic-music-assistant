# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os

import google.auth
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from google.cloud import logging as google_cloud_logging

from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback

setup_telemetry()
_, project_id = google.auth.default()
logging_client = google_cloud_logging.Client()
logger = logging_client.logger(__name__)
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

# Artifact bucket for ADK (created by Terraform, passed via env var)
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# In-memory session configuration - no persistent storage
session_service_uri = None

artifact_service_uri = f"gs://{logs_bucket_name}" if logs_bucket_name else None

app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=artifact_service_uri,
    allow_origins=allow_origins,
    session_service_uri=session_service_uri,
    otel_to_cloud=True,
)
app.title = "cadence"
app.description = "API for interacting with Cadence, the AI music assistant"


from fastapi.staticfiles import StaticFiles
from app.app_utils.visual_runner import VisualRunner

# Mount skills static files
skills_dir = os.path.join(AGENT_DIR, "skills")
app.mount("/dev-ui/skills", StaticFiles(directory=skills_dir), name="dev_ui_skills")
app.mount("/skills", StaticFiles(directory=skills_dir), name="skills")

# Replace default runner with VisualRunner if present
if hasattr(app, "state") and hasattr(app.state, "runner") and app.state.runner:
    existing_runner = app.state.runner
    app.state.runner = VisualRunner(
        app=existing_runner.app,
        session_service=existing_runner.session_service,
        artifact_service=existing_runner.artifact_service,
        auto_create_session=existing_runner.auto_create_session,
    )

@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    try:
        logger.log_struct(feedback.model_dump(), severity="INFO")
    except Exception as e:
        import logging
        logging.warning(f"Failed to log feedback to Google Cloud Logging: {e}")
    return {"status": "success"}


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
