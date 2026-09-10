from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

class QueryRequestDTO(BaseModel):
    query: str = Field(..., json_schema_extra={"example": "What is the spending limit for Level 1 procurement agents?"})
    experiment_mode: Literal["E0", "E1", "E2", "E3"] = Field("E0", description="Controlled experiment mode")
    user_role: str = Field("procurement_agent", description="User financial delegation role")
    trace_id: Optional[str] = None

class ExecutionMetricsDTO(BaseModel):
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    tool_calls_count: int

class QueryResponseDTO(BaseModel):
    trace_id: str
    experiment_mode: str
    user_role: str
    answer: str
    status: Literal["COMPLETED", "ESCALATED", "BLOCKED", "MAX_ITERATIONS", "ERROR", "TIMEOUT"]
    escalation_triggered: bool = False
    escalation_reason: Optional[str] = None
    metrics: ExecutionMetricsDTO

class ExperimentRunRequestDTO(BaseModel):
    modes: List[str] = Field(default_factory=lambda: ["E0", "E1", "E2", "E3"])
