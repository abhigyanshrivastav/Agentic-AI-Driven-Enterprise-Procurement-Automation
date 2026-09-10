import pytest
from src.agent.graph import AgentOrchestrator

def test_agent_orchestrator_e0():
    orchestrator = AgentOrchestrator()
    state = orchestrator.run(
        query="What is the standard return policy?",
        experiment_mode="E0",
        user_role="procurement_agent"
    )
    assert state["experiment_mode"] == "E0"
    assert state["status"] == "COMPLETED"
    assert len(state["final_response"]) > 0

def test_agent_orchestrator_e3_escalation():
    orchestrator = AgentOrchestrator()
    state = orchestrator.run(
        query="Create a purchase order for 20 units of SKU-1001 (unit price $870.00) from SUP-101.",
        experiment_mode="E3",
        user_role="procurement_agent"
    )
    assert state["experiment_mode"] == "E3"
    assert state["status"] == "ESCALATED"
    assert state["escalation_triggered"] is True
    assert "Financial Spend Threshold Exceeded" in state["escalation_reason"]
