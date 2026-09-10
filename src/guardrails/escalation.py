import uuid
import datetime
from typing import Dict, Any
from pydantic import BaseModel

class EscalationTicket(BaseModel):
    ticket_id: str
    trace_id: str
    query: str
    reason: str
    user_role: str
    timestamp: str
    status: str = "OPEN_FOR_HUMAN_REVIEW"

def create_human_escalation_ticket(trace_id: str, query: str, reason: str, user_role: str) -> EscalationTicket:
    ticket_id = f"ESC-{uuid.uuid4().hex[:6].upper()}"
    return EscalationTicket(
        ticket_id=ticket_id,
        trace_id=trace_id,
        query=query,
        reason=reason,
        user_role=user_role,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
