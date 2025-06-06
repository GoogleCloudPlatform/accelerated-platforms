# my_gaming_agent/models.py

from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class AgentPrompt(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    # Add the missing field here:
    is_content_generation: bool = False # Default to False

class AgentResponse(BaseModel):
    response_text: str
    session_id: Optional[str] = None
    tool_outputs: Optional[Dict[str, Any]] = None # Tool outputs can be flexible JSON

# If you still have ContentGenerationRequest and ContentGenerationResponse,
# you should remove them if they are no longer used, as we've consolidated
# the logic into /ask_agent.
# Example:
# class ContentGenerationRequest(BaseModel):
#     content_type: str
#     dialogue: str
#     session_id: Optional[str] = None

# class ContentGenerationResponse(BaseModel):
#     url: str
#     message: str
#     session_id: Optional[str] = None
