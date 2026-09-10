from pydantic import BaseModel, ValidationError
from typing import Optional, Tuple

class ValidatedAgentOutput(BaseModel):
    summary: str
    action_taken: Optional[str] = None
    policy_reference: Optional[str] = None

def validate_agent_output(text_output: str) -> Tuple[bool, str, Optional[ValidatedAgentOutput]]:
    """Validates that final model output conforms to basic structured output requirements."""
    if not text_output or len(text_output.strip()) == 0:
        return False, "Output Validation Failed: Empty model response.", None

    validated = ValidatedAgentOutput(
        summary=text_output.strip(),
        action_taken="information_provided"
    )
    return True, "Output validation passed.", validated
