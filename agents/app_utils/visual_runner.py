import re
import sys
from pathlib import Path
from google.adk.runners import Runner
from google.genai import types

# Resolve project root
_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

class VisualRunner(Runner):
    """A custom ADK Runner that automatically detects markdown image links pointing to

    local assets in the agent's text responses and appends them as binary image parts
    to create a multipart response (text + image).
    """
    async def run_async(self, *args, **kwargs):
        async for event in super().run_async(*args, **kwargs):
            if hasattr(event, "message") and event.message and event.message.parts:
                new_parts = list(event.message.parts)
                image_added = False
                
                for part in event.message.parts:
                    if part.text:
                        # Find all relative markdown image paths pointing to the assets directory
                        matches = re.findall(
                            r'!\[.*?\]\((skills/visual_notation_rendering/assets/[a-zA-Z0-9_\-\.]+)\)',
                            part.text
                        )
                        for img_rel_path in matches:
                            img_path = Path(img_rel_path)
                            abs_path = _PROJECT_ROOT / img_path
                            if abs_path.is_file():
                                try:
                                    with open(abs_path, "rb") as f:
                                        img_bytes = f.read()
                                    # Create the inline image part
                                    image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/png")
                                    new_parts.append(image_part)
                                    image_added = True
                                    print(f"[VisualRunner] Attached binary image part for: {img_rel_path}")
                                except Exception as e:
                                    print(f"[VisualRunner] Failed to read image file {abs_path}: {e}")
                                    
                if image_added:
                    event.message.parts = new_parts
                    
            yield event
