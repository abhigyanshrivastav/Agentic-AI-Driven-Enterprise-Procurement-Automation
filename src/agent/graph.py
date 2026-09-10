import uuid
import time
from typing import Dict, Any, Optional
from src.agent.state import AgentState
from src.agent.nodes import (
    input_guard_node,
    retrieval_node,
    model_node,
    guardrail_auth_node,
    tool_execution_node,
    output_guard_node
)
from src.config import get_settings, is_valid_api_key
from src.observability import logger

class AgentOrchestrator:
    """Orchestrates query execution across E0, E1, E2, and E3 experimental configurations."""

    def __init__(self, require_live_api: bool = False, force_mock: bool = False):
        settings = get_settings()
        self.max_agent_iterations = settings.max_agent_iterations
        self.require_live_api = require_live_api
        self.force_mock = force_mock
        
        has_key = is_valid_api_key(settings.llm_api_key)
        if require_live_api and not has_key:
            raise ValueError("AgentOrchestrator initialized with require_live_api=True, but no valid API key was found!")

        if require_live_api and not force_mock:
            self.execution_mode = "LIVE_API"
        else:
            self.execution_mode = "OFFLINE_MOCK"

    def run(
        self,
        query: str,
        experiment_mode: str = "E0",
        user_role: str = "procurement_agent",
        trace_id: Optional[str] = None
    ) -> AgentState:
        start_time = time.perf_counter()
        tid = trace_id or f"TR-{uuid.uuid4().hex[:8].upper()}"

        state: AgentState = {
            "trace_id": tid,
            "query": query,
            "experiment_mode": experiment_mode,
            "user_role": user_role,
            "execution_mode": self.execution_mode,
            "retrieved_context": [],
            "retrieved_doc_ids": [],
            "retrieved_chunk_ids": [],
            "messages": [],
            "agent_iteration_count": 0,
            "llm_call_count": 0,
            "tool_call_count": 0,
            "termination_reason": "COMPLETED",
            "selected_tool_calls": [],
            "executed_tool_calls": [],
            "blocked_tool_calls": [],
            "tool_calls": [],
            "tool_results": [],
            "authorization_decisions": [],
            "input_safety_passed": True,
            "authorization_passed": True,
            "guardrail_violations": [],
            "escalation_triggered": False,
            "escalation_reason": None,
            "final_response": "",
            "status": "COMPLETED",
            "metrics": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "estimated_cost_usd": 0.0,
                "latency_ms": 0.0,
                "tool_calls_count": 0
            }
        }

        logger.info(f"[{tid}] Starting query execution in mode '{experiment_mode}' for role '{user_role}' ({self.execution_mode})")

        # 1. Input Guard (E3 mode)
        state = input_guard_node(state)
        if state["status"] == "BLOCKED":
            state["termination_reason"] = "BLOCKED"
            state["metrics"]["latency_ms"] = round((time.perf_counter() - start_time) * 1000.0, 2)
            return state

        # 2. RAG Retrieval (E1, E2, E3 modes)
        state = retrieval_node(state)

        # 3. Agent Execution Loop with Bounded Iterations
        while state["agent_iteration_count"] < self.max_agent_iterations:
            state["agent_iteration_count"] += 1
            
            # Model Call
            state = model_node(state)
            
            # Check for Guardrail / Auth Interception (E3)
            if state["experiment_mode"] == "E3" and state["selected_tool_calls"]:
                state = guardrail_auth_node(state)
                if not state["authorization_passed"]:
                    break

            # Execute Tools if selected and authorized
            if state["selected_tool_calls"] and state.get("authorization_passed", True):
                unexecuted = [tc for tc in state["selected_tool_calls"] if tc not in state["executed_tool_calls"]]
                if unexecuted:
                    state = tool_execution_node(state)
                    state["metrics"]["tool_calls_count"] = len(state["executed_tool_calls"])
                else:
                    break
            else:
                break

        # Check if max iteration limit was reached
        if state["agent_iteration_count"] >= self.max_agent_iterations and state["selected_tool_calls"] and [tc for tc in state["selected_tool_calls"] if tc not in state["executed_tool_calls"]]:
            state["status"] = "MAX_ITERATIONS"
            state["termination_reason"] = "MAX_ITERATIONS"
            logger.warning(f"[{tid}] Agent iteration bound reached (max={self.max_agent_iterations})")

        # 4. Output Validation (E3 mode)
        if state["status"] == "COMPLETED":
            state = output_guard_node(state)

        total_latency = (time.perf_counter() - start_time) * 1000.0
        state["metrics"]["latency_ms"] = round(total_latency, 2)

        logger.info(f"[{tid}] Execution finished: status='{state['status']}', reason='{state['termination_reason']}' in {total_latency:.2f}ms")
        return state
