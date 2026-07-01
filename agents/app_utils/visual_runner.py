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
        # Extract session_id from arguments
        session_id = kwargs.get("session_id")
        if not session_id and len(args) > 1:
            session_id = args[1]
            
        async for event in super().run_async(*args, **kwargs):
            if hasattr(event, "message") and event.message and event.message.parts:
                new_parts = []
                image_added = False
                
                for part in event.message.parts:
                    if part.text:
                        text_content = part.text
                        # If a session_id is available, resolve any placeholder references like SESSION_ID or <session_id>
                        if session_id:
                            text_content = re.sub(
                                r'(skills/visual_notation_rendering/assets/chord_)(?:SESSION_ID|<session_id>|\{session_id\})(\.png)',
                                fr'\g<1>{session_id}\2',
                                text_content
                            )
                            # Also update the part text with the corrected path
                            part.text = text_content
                            
                        # Find all relative markdown image paths pointing to the assets directory
                        matches = re.findall(
                            r'!\[.*?\]\((skills/visual_notation_rendering/assets/[a-zA-Z0-9_\-\.]+)\)',
                            text_content
                        )
                        new_parts.append(part)
                        
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
                                    print(f"[VisualRunner] Resolved placeholder and attached binary image part for: {img_rel_path}")
                                except Exception as e:
                                    print(f"[VisualRunner] Failed to read image file {abs_path}: {e}")
                            else:
                                print(f"[VisualRunner] Image file not found: {abs_path}")
                    else:
                        new_parts.append(part)
                                    
                if image_added:
                    event.message.parts = new_parts
                    
            yield event
