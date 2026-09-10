import json
import time
from typing import Dict, Any, List
from src.agent.state import AgentState
from src.llm.client import LLMClient, ProviderQuotaError
from src.llm.embeddings import EmbeddingClient
from src.rag.retriever import FAISSRetriever
from src.tools.registries import PROCUREMENT_TOOLS_SCHEMA, dispatch_tool_call
from src.guardrails.authorization import DeterministicAuthorizer
from src.guardrails.input_guard import check_input_safety
from src.guardrails.output_validator import validate_agent_output
from src.guardrails.escalation import create_human_escalation_ticket
from src.observability import logger

retriever = FAISSRetriever()
llm_client = LLMClient()
authorizer = DeterministicAuthorizer()

def input_guard_node(state: AgentState) -> AgentState:
    """Evaluates input query safety in E3 mode."""
    if state["experiment_mode"] == "E3":
        passed, msg = check_input_safety(state["query"])
        state["input_safety_passed"] = passed
        if not passed:
            state["status"] = "BLOCKED"
            state["termination_reason"] = "BLOCKED"
            state["final_response"] = f"Request Blocked: {msg}"
            state["guardrail_violations"].append(msg)
            logger.warning(f"[{state['trace_id']}] Input guard blocked query: {msg}")
    else:
        state["input_safety_passed"] = True
    return state

def retrieval_node(state: AgentState) -> AgentState:
    """Retrieves policy context and metadata from FAISS for E1, E2, E3 modes. Enforces RAG retrieval gating."""
    mode = state["experiment_mode"]
    if mode in ["E1", "E2", "E3"]:
        try:
            exec_mode = state.get("execution_mode", "OFFLINE_MOCK")
            node_emb_client = EmbeddingClient(
                require_live_api=(exec_mode == "LIVE_API"),
                force_mock=(exec_mode == "OFFLINE_MOCK")
            )
            node_retriever = FAISSRetriever(embedding_client=node_emb_client)
            chunks = node_retriever.retrieve(state["query"], top_k=4)
        except Exception as e:
            state["retrieved_context"] = []
            state["retrieved_doc_ids"] = []
            state["retrieved_chunk_ids"] = []
            state["status"] = "ERROR"
            state["termination_reason"] = "PROVIDER_EMBEDDING_ERROR" if "PROVIDER_EMBEDDING_ERROR" in str(e) else "RAG_INDEX_ERROR"
            state["final_response"] = str(e)
            logger.error(f"[{state['trace_id']}] RAG Retrieval Exception: {e}")
            return state

        if not chunks:
            state["retrieved_context"] = []
            state["retrieved_doc_ids"] = []
            state["retrieved_chunk_ids"] = []
            state["status"] = "ERROR"
            state["termination_reason"] = "RAG_INDEX_ERROR"
            logger.error(f"[{state['trace_id']}] RAG Smoke-Gate Failure: Retrieved 0 chunks for mode {mode}")
            return state

        context_texts = [c.content for c in chunks]
        doc_ids = list(dict.fromkeys([c.doc_id for c in chunks if c.doc_id]))
        chunk_ids = list(dict.fromkeys([c.chunk_id for c in chunks if c.chunk_id]))
        
        state["retrieved_context"] = context_texts
        state["retrieved_doc_ids"] = doc_ids
        state["retrieved_chunk_ids"] = chunk_ids
        logger.info(f"[{state['trace_id']}] Retrieved {len(context_texts)} context chunks for mode {mode}")
    else:
        state["retrieved_context"] = []
        state["retrieved_doc_ids"] = []
        state["retrieved_chunk_ids"] = []
    return state

def model_node(state: AgentState) -> AgentState:
    """Invokes LLM with prompts, RAG context, and tools depending on mode."""
    mode = state["experiment_mode"]
    
    if state.get("status") in ["BLOCKED", "ESCALATED", "ERROR", "TIMEOUT", "MAX_ITERATIONS"]:
        return state

    context_str = "\n---\n".join(state["retrieved_context"]) if state["retrieved_context"] else "None"
    
    system_prompt = "You are an Enterprise Procurement Assistant."
    if mode == "E0":
        system_prompt = "You are an Enterprise Procurement Assistant. Answer the query directly using general knowledge."
    elif mode == "E1":
        system_prompt = f"You are an Enterprise Procurement Assistant. Use ONLY the retrieved context below to answer.\nContext:\n{context_str}"
    elif mode == "E2":
     system_prompt = (
        f"You are an Enterprise Procurement Agent. "
        f"Use retrieved context and available tools to fulfill requests. "
        f"When the user explicitly requests a purchase order, create the purchase order "
        f"using the create_purchase_order tool with the requested SKU, quantity, supplier, "
        f"and unit price.\nContext:\n{context_str}"
    )
    elif mode == "E3":
        system_prompt = (
            f"You are an Enterprise Procurement Agent operating under enterprise guardrails. "
            f"Use retrieved context and available tools to fulfill the user's request. "
            f"When the user explicitly requests a purchase order, attempt to create the purchase "
            f"order using the create_purchase_order tool with the exact requested SKU, quantity, "
            f"supplier, and unit price. Do not substitute the purchase-order request with only "
            f"inventory or supplier lookup. Authorization is enforced separately by the "
            f"deterministic guardrail layer.\nContext:\n{context_str}"
        )

    messages = [{"role": "system", "content": system_prompt}]
    
    if not state["messages"]:
        state["messages"].append({"role": "user", "content": state["query"]})

    messages.extend(state["messages"])

    tools = PROCUREMENT_TOOLS_SCHEMA if mode in ["E2", "E3"] else None

    if mode == "E3" and "purchase order" in state["query"].lower():
        tools = [
            tool for tool in PROCUREMENT_TOOLS_SCHEMA
            if tool["function"]["name"] == "create_purchase_order"
        ]

    state["llm_call_count"] += 1
    
    try:
        exec_mode = state.get("execution_mode", "OFFLINE_MOCK")
        client = LLMClient(
            require_live_api=(exec_mode == "LIVE_API"),
            force_mock=(exec_mode == "OFFLINE_MOCK")
        )
        llm_resp = client.generate(messages=messages, tools=tools)
    except ProviderQuotaError as e:
        state["status"] = "ERROR"
        state["termination_reason"] = "PROVIDER_QUOTA_ERROR"
        state["final_response"] = str(e)
        state["selected_tool_calls"] = []
        logger.error(f"[{state['trace_id']}] Provider Quota Error: {e}")
        return state
    except Exception as e:
        state["status"] = "ERROR"
        state["termination_reason"] = "PROVIDER_ERROR"
        state["final_response"] = str(e)
        state["selected_tool_calls"] = []
        logger.error(f"[{state['trace_id']}] Provider Call Error: {e}")
        return state

    current_metrics = state.get("metrics", {})
    current_metrics["prompt_tokens"] = current_metrics.get("prompt_tokens", 0) + llm_resp.prompt_tokens
    current_metrics["completion_tokens"] = current_metrics.get("completion_tokens", 0) + llm_resp.completion_tokens
    current_metrics["estimated_cost_usd"] = current_metrics.get("estimated_cost_usd", 0.0) + llm_resp.estimated_cost_usd
    current_metrics["latency_ms"] = current_metrics.get("latency_ms", 0.0) + llm_resp.latency_ms
    state["metrics"] = current_metrics

    assistant_message = {
        "role": "assistant",
        "content": llm_resp.content or ""
    }

    if llm_resp.tool_calls:
        assistant_message["tool_calls"] = llm_resp.tool_calls

    state["messages"].append(assistant_message)
    state["final_response"] = llm_resp.content

    if llm_resp.tool_calls:
        state["selected_tool_calls"].extend(llm_resp.tool_calls)
        state["tool_calls"].extend(llm_resp.tool_calls)
        logger.info(f"[{state['trace_id']}] LLM emitted {len(llm_resp.tool_calls)} tool calls")
    else:
        state["status"] = "COMPLETED"
        state["termination_reason"] = "COMPLETED"

    return state

def guardrail_auth_node(state: AgentState) -> AgentState:
    """Evaluates authorization before tool execution in E3 mode."""
    if state.get("status") == "ERROR":
        return state

    if state["experiment_mode"] != "E3" or not state["selected_tool_calls"]:
        state["authorization_passed"] = True
        return state

    for tc in state["selected_tool_calls"]:
        func_name = tc["function"]["name"]
        args_raw = tc["function"]["arguments"]
        args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw

        if func_name == "create_purchase_order":
            decision = authorizer.authorize_purchase_order(
                sku=args.get("sku", ""),
                qty=int(args.get("qty", 1)),
                unit_price=float(args.get("unit_price", 0.0)),
                supplier_id=args.get("supplier_id", ""),
                user_role=state["user_role"]
            )
            
            state["authorization_decisions"].append({
                "tool": func_name,
                "args": args,
                "authorized": decision.authorized,
                "requires_human_escalation": decision.requires_human_escalation,
                "reason": decision.reason
            })

            if not decision.authorized:
                state["authorization_passed"] = False
                state["blocked_tool_calls"].append(tc)
                state["escalation_triggered"] = decision.requires_human_escalation
                state["escalation_reason"] = decision.reason
                state["status"] = "ESCALATED" if decision.requires_human_escalation else "BLOCKED"
                state["termination_reason"] = "ESCALATED" if decision.requires_human_escalation else "BLOCKED"
                
                ticket = create_human_escalation_ticket(
                    trace_id=state["trace_id"],
                    query=state["query"],
                    reason=decision.reason,
                    user_role=state["user_role"]
                )
                state["final_response"] = f"Action Escalated: {decision.reason} (Ticket ID: {ticket.ticket_id})"
                state["guardrail_violations"].append(decision.reason)
                logger.warning(f"[{state['trace_id']}] Authorization blocked/escalated PO creation: {decision.reason}")
                return state

    state["authorization_passed"] = True
    return state

def tool_execution_node(state: AgentState) -> AgentState:
    """Executes tool calls if authorization passed."""
    if state.get("status") == "ERROR":
        return state

    if not state["selected_tool_calls"] or (state["experiment_mode"] == "E3" and not state["authorization_passed"]):
        return state

    results = []
    executed = []
    already_executed_ids = {tc.get("id") for tc in state["executed_tool_calls"]}
    
    for tc in state["selected_tool_calls"]:
        tc_id = tc.get("id")
        if tc_id in already_executed_ids:
            continue

        func_name = tc["function"]["name"]
        args_raw = tc["function"]["arguments"]
        args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw

        try:
            res = dispatch_tool_call(func_name, args, user_role=state["user_role"])
            results.append({
                "tool_name": func_name,
                "success": res.success,
                "data": res.data,
                "message": res.message,
                "error": res.error
            })
            executed.append(tc)
            
            tool_content = json.dumps(res.data) if (res.success and res.data) else (res.message if res.success else f"Error: {res.error}")
            state["messages"].append({
                "role": "tool",
                "tool_call_id": tc_id or "call_01",
                "name": func_name,
                "content": tool_content
            })

            if not res.success:
                state["status"] = "ERROR"
                state["termination_reason"] = "DATABASE_SCHEMA_ERROR" if "no such table" in str(res.error).lower() else "TOOL_ERROR"
            logger.info(f"[{state['trace_id']}] Executed tool '{func_name}': Success={res.success}")
        except Exception as e:
            state["status"] = "ERROR"
            state["termination_reason"] = "DATABASE_SCHEMA_ERROR" if "no such table" in str(e).lower() else "TOOL_ERROR"
            logger.error(f"Tool execution exception for '{func_name}': {e}")
            return state

    state["tool_results"].extend(results)
    state["executed_tool_calls"].extend(executed)
    state["tool_call_count"] = len(state["executed_tool_calls"])
    
    tool_messages = [r["message"] if r["success"] else f"Error: {r['error']}" for r in results]
    if tool_messages:
        state["final_response"] = "\n".join(tool_messages)
    if state["status"] != "ERROR":
        state["status"] = "COMPLETED"
        state["termination_reason"] = "COMPLETED"
    return state

def output_guard_node(state: AgentState) -> AgentState:
    """Validates final agent output in E3 mode."""
    if state["experiment_mode"] == "E3" and state["status"] == "COMPLETED":
        passed, msg, validated = validate_agent_output(state["final_response"])
        if not passed:
            state["status"] = "BLOCKED"
            state["termination_reason"] = "BLOCKED"
            state["guardrail_violations"].append(msg)
            logger.warning(f"[{state['trace_id']}] Output guard validation failed: {msg}")
    return state
