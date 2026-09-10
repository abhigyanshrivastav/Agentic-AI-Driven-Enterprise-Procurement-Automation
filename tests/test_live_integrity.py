import pytest
from unittest.mock import patch
from src.llm.client import LLMClient, ProviderQuotaError
from src.agent.graph import AgentOrchestrator
from src.evaluation.metrics_eval import evaluate_task_success, evaluate_execution_completion

def test_live_provider_quota_error_fails_fast_non_retryable():
    with patch("litellm.completion") as mock_comp:
        mock_comp.side_effect = Exception("RateLimitError: OpenAIException - You exceeded your current quota")
        client = LLMClient(model_name="gpt-4o-mini", require_live_api=True)
        client.api_key = "sk-fake-valid-key-for-test"
        
        with pytest.raises(ProviderQuotaError, match="PROVIDER_QUOTA_ERROR"):
            client.generate([{"role": "user", "content": "hello"}])
        
        assert mock_comp.call_count == 1

def test_live_provider_failure_sets_status_error_and_no_tools():
    orchestrator = AgentOrchestrator()
    orchestrator.execution_mode = "LIVE_API"
    
    with patch("src.agent.nodes.LLMClient") as mock_client_cls, \
         patch("src.agent.nodes.EmbeddingClient") as mock_embed_cls:
        mock_embed = mock_embed_cls.return_value
        mock_embed.get_embeddings.return_value = [[0.0] * 768]
        mock_client = mock_client_cls.return_value
        mock_client.generate.side_effect = ProviderQuotaError("PROVIDER_QUOTA_ERROR: Quota exceeded")
        
        state = orchestrator.run(
            query="Create a purchase order for 10 units of SKU-1001",
            experiment_mode="E2"
        )
        
        assert state["status"] == "ERROR"
        assert state["termination_reason"] == "PROVIDER_QUOTA_ERROR"
        assert len(state["selected_tool_calls"]) == 0
        assert len(state["executed_tool_calls"]) == 0

def test_live_provider_failure_task_success_zero():
    assert evaluate_task_success(actual_status="ERROR", expected_final_status="COMPLETED") == 0.0
    assert evaluate_execution_completion(actual_status="ERROR") == 0.0

def test_offline_mock_mode_still_works():
    orchestrator = AgentOrchestrator(require_live_api=False)
    state = orchestrator.run(query="What is the return policy?", experiment_mode="E0")
    assert state["status"] == "COMPLETED"
    assert len(state["final_response"]) > 0

def test_gemini_2_5_flash_model_resolution():
    client = LLMClient(model_name="gemini-2.5-flash", require_live_api=True)
    client.api_key = "AIzaSyTestFakeKeyForUnitTesting123456"
    client.provider = "gemini"
    
    with patch("litellm.completion") as mock_comp:
        mock_comp.return_value = type("DummyResponse", (), {
            "choices": [type("Choice", (), {"message": type("Msg", (), {"content": "ok", "tool_calls": None})()})()],
            "usage": type("Usage", (), {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})()
        })()
        
        client.generate([{"role": "user", "content": "hello"}])
        
        assert mock_comp.call_count == 1
        call_kwargs = mock_comp.call_args.kwargs
        assert call_kwargs["model"] == "gemini/gemini-2.5-flash"
        assert "3.6" not in call_kwargs["model"]
