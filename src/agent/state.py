from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict

class AgentState(TypedDict):
    trace_id: str
    query: str
    experiment_mode: str  # "E0", "E1", "E2", "E3"
    user_role: str        # "procurement_agent", "manager", "admin"
    execution_mode: str   # "OFFLINE_MOCK" or "LIVE_API"
    
    # RAG Context & Metadata
    retrieved_context: List[str]
    retrieved_doc_ids: List[str]
    retrieved_chunk_ids: List[str]
    
    # LLM conversation history
    messages: List[Dict[str, Any]]
    
    # Execution & Request Counters
    agent_iteration_count: int
    llm_call_count: int
    tool_call_count: int
    termination_reason: str # "COMPLETED", "ESCALATED", "BLOCKED", "MAX_ITERATIONS", "ERROR", "TIMEOUT"
    
    # Tool execution breakdown
    selected_tool_calls: List[Dict[str, Any]]
    executed_tool_calls: List[Dict[str, Any]]
    blocked_tool_calls: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]       # Legacy alias for executed_tool_calls
    tool_results: List[Dict[str, Any]]
    
    # Safety & Control Traces
    authorization_decisions: List[Dict[str, Any]]
    input_safety_passed: bool
    authorization_passed: bool
    guardrail_violations: List[str]
    escalation_triggered: bool
    escalation_reason: Optional[str]
    
    # Final Output & Metrics
    final_response: str
    status: str           # "SUCCESS", "GUARDRAIL_BLOCKED", "ESCALATED", "ERROR"
    metrics: Dict[str, Any]
