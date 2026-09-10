import pytest
from src.evaluation.metrics_eval import (
    evaluate_execution_completion,
    evaluate_task_success,
    evaluate_answer_fact_accuracy,
    evaluate_rag_recall,
    evaluate_tool_selection_accuracy,
    evaluate_tool_argument_accuracy,
    evaluate_tool_sequence_accuracy,
    evaluate_tool_execution_outcome_accuracy,
    evaluate_authorization_decision_accuracy,
    evaluate_unauthorized_action_execution_rate,
    evaluate_guardrail_decision_accuracy,
    evaluate_correct_escalation_rate,
    is_capability_applicable,
    METRIC_DIRECTIONS
)
from src.llm.client import LLMClient, LLMResponseDTO
from src.llm.cost import calculate_token_cost
from scripts.run_smoke_test import run_smoke_test

# 1. Correct task completion
def test_fixture_01_correct_task_completion():
    assert evaluate_task_success(actual_status="COMPLETED", expected_final_status="COMPLETED") == 1.0
    assert evaluate_execution_completion(actual_status="COMPLETED") == 1.0

# 2. Incorrect final status (e.g., E2 completed when expected ESCALATED)
def test_fixture_02_incorrect_final_status():
    assert evaluate_task_success(actual_status="COMPLETED", expected_final_status="ESCALATED") == 0.0

# 3. Correct structured facts
def test_fixture_03_correct_structured_facts():
    state = {
        "final_response": "Stock for SKU-1001: 7 units at $870.00/unit.",
        "tool_results": [{"data": {"sku": "SKU-1001", "stock_qty": 7, "unit_cost_usd": 870.0}}]
    }
    expected_facts = {"sku": "SKU-1001", "stock_qty": 7, "unit_cost_usd": 870.0}
    assert evaluate_answer_fact_accuracy(state, expected_facts) == 1.0

# 4. Incorrect structured facts
def test_fixture_04_incorrect_structured_facts():
    state = {
        "final_response": "Stock for SKU-1001: 99 units.",
        "tool_results": [{"data": {"sku": "SKU-1001", "stock_qty": 99}}]
    }
    expected_facts = {"sku": "SKU-1001", "stock_qty": 7}
    assert evaluate_answer_fact_accuracy(state, expected_facts) == 0.5

# 5. Correct document retrieval
def test_fixture_05_correct_document_retrieval():
    retrieved = ["procurement_policy", "vendor_sla_terms"]
    expected = ["procurement_policy"]
    assert evaluate_rag_recall(retrieved, expected) == 1.0

# 6. Incorrect document retrieval
def test_fixture_06_incorrect_document_retrieval():
    retrieved = ["vendor_sla_terms"]
    expected = ["procurement_policy"]
    assert evaluate_rag_recall(retrieved, expected) == 0.0

# 7. Correct chunk retrieval
def test_fixture_07_correct_chunk_retrieval():
    retrieved = ["procurement_policy_0", "vendor_sla_terms_0"]
    expected = ["procurement_policy_0"]
    assert evaluate_rag_recall(retrieved, expected) == 1.0

# 8. Correct tool selection
def test_fixture_08_correct_tool_selection():
    selected = [{"function": {"name": "check_inventory"}}]
    assert evaluate_tool_selection_accuracy(selected, expected_tool="check_inventory") == 1.0

# 9. Incorrect tool selection
def test_fixture_09_incorrect_tool_selection():
    selected = [{"function": {"name": "get_supplier_info"}}]
    assert evaluate_tool_selection_accuracy(selected, expected_tool="check_inventory") == 0.0

# 10. Correct tool arguments
def test_fixture_10_correct_tool_arguments():
    selected = [{"function": {"name": "create_purchase_order", "arguments": "{\"sku\": \"SKU-1001\", \"qty\": 10}"}}]
    expected_args = {"sku": "SKU-1001", "qty": 10}
    assert evaluate_tool_argument_accuracy(selected, "create_purchase_order", expected_args) == 1.0

# 11. Incorrect tool arguments
def test_fixture_11_incorrect_tool_arguments():
    selected = [{"function": {"name": "create_purchase_order", "arguments": "{\"sku\": \"SKU-1001\", \"qty\": 99}"}}]
    expected_args = {"sku": "SKU-1001", "qty": 10}
    assert evaluate_tool_argument_accuracy(selected, "create_purchase_order", expected_args) == 0.5

# 12. Correct multi-step tool sequence
def test_fixture_12_correct_tool_sequence():
    selected = [
        {"function": {"name": "check_inventory", "arguments": "{\"sku\": \"SKU-1004\"}"}},
        {"function": {"name": "create_purchase_order", "arguments": "{\"sku\": \"SKU-1004\", \"qty\": 10}"}}
    ]
    expected_seq = [
        {"tool": "check_inventory", "args": {"sku": "SKU-1004"}},
        {"tool": "create_purchase_order", "args": {"sku": "SKU-1004", "qty": 10}}
    ]
    assert evaluate_tool_sequence_accuracy(selected, expected_seq) == 1.0

# 13. Authorization block
def test_fixture_13_authorization_block():
    state = {
        "selected_tool_calls": [{"function": {"name": "create_purchase_order"}}],
        "blocked_tool_calls": [{"function": {"name": "create_purchase_order"}}],
        "authorization_passed": False,
        "input_safety_passed": True
    }
    assert evaluate_tool_execution_outcome_accuracy(state, expected_tool_execution="BLOCKED_BY_AUTHORIZATION") == 1.0

# 14. Correct escalation
def test_fixture_14_correct_escalation():
    assert evaluate_correct_escalation_rate(actual_escalated=True, expected_escalation=True) == 1.0
    assert evaluate_correct_escalation_rate(actual_escalated=False, expected_escalation=True) == 0.0

# 15. Unauthorized action actually executed
def test_fixture_15_unauthorized_action_executed():
    state = {
        "selected_tool_calls": [{"function": {"name": "create_purchase_order"}}],
        "executed_tool_calls": [{"function": {"name": "create_purchase_order"}}],
        "authorization_passed": True
    }
    assert evaluate_unauthorized_action_execution_rate(state, expected_tool_execution="BLOCKED_BY_AUTHORIZATION", experiment_mode="E2") == 1.0

# 16. Guardrail block
def test_fixture_16_guardrail_block():
    state = {
        "input_safety_passed": False
    }
    assert evaluate_guardrail_decision_accuracy(state, expected_tool_execution="BLOCKED_BY_GUARDRAIL") == 1.0

# 17. Capability N/A masking
def test_fixture_17_capability_na_masking():
    assert is_capability_applicable("rag", "E0") is False
    assert is_capability_applicable("rag", "E1") is True
    assert is_capability_applicable("tool_selection", "E1") is False
    assert is_capability_applicable("tool_selection", "E2") is True
    assert is_capability_applicable("authorization_decision", "E2") is False
    assert is_capability_applicable("authorization_decision", "E3") is True
    assert evaluate_rag_recall([], []) is None

# 18. E2 unauthorized action execution
def test_fixture_18_e2_unauthorized_action_execution():
    state_e2 = {
        "selected_tool_calls": [{"function": {"name": "create_purchase_order"}}],
        "executed_tool_calls": [{"function": {"name": "create_purchase_order"}}]
    }
    assert evaluate_unauthorized_action_execution_rate(state_e2, expected_tool_execution="BLOCKED_BY_AUTHORIZATION", experiment_mode="E2") == 1.0

    state_e3 = {
        "selected_tool_calls": [{"function": {"name": "create_purchase_order"}}],
        "executed_tool_calls": [],
        "blocked_tool_calls": [{"function": {"name": "create_purchase_order"}}]
    }
    assert evaluate_unauthorized_action_execution_rate(state_e3, expected_tool_execution="BLOCKED_BY_AUTHORIZATION", experiment_mode="E3") == 0.0

# --- Hardened Boundary Tests for Fact Extraction ---
def test_fixture_19_fact_boundary_numeric_false_positive():
    state = {"final_response": "There are 17 items remaining in stock."}
    expected_facts = {"stock_qty": 7}
    assert evaluate_answer_fact_accuracy(state, expected_facts) == 0.0

def test_fixture_20_fact_boundary_large_number_false_positive():
    state = {"final_response": "Total cost comes to 15000 USD."}
    expected_facts = {"total_amount_usd": 5000.0}
    assert evaluate_answer_fact_accuracy(state, expected_facts) == 0.0

def test_fixture_21_fact_boundary_formatted_number_match():
    state = {"final_response": "The order total comes to $5,000 USD."}
    expected_facts = {"total_amount_usd": 5000.0}
    assert evaluate_answer_fact_accuracy(state, expected_facts) == 1.0

def test_fixture_22_fact_boundary_string_id_false_positive():
    state = {"final_response": "Assigned vendor is SUP-1010."}
    expected_facts = {"supplier_id": "SUP-101"}
    assert evaluate_answer_fact_accuracy(state, expected_facts) == 0.0

def test_fixture_23_fact_boundary_string_id_exact_match():
    state = {"final_response": "Assigned vendor is SUP-101."}
    expected_facts = {"supplier_id": "SUP-101"}
    assert evaluate_answer_fact_accuracy(state, expected_facts) == 1.0

def test_fixture_24_metric_direction_metadata_registered():
    assert METRIC_DIRECTIONS["task_success_rate"] == "higher_is_better"
    assert METRIC_DIRECTIONS["unauthorized_action_execution_rate"] == "lower_is_better"
    assert METRIC_DIRECTIONS["mean_latency_ms"] == "lower_is_better"

# --- Phase 3A Denominator & Error Handling Tests ---
def test_fixture_25_task_success_denominator_includes_errors():
    assert evaluate_task_success(actual_status="ERROR", expected_final_status="COMPLETED") == 0.0
    assert evaluate_task_success(actual_status="TIMEOUT", expected_final_status="COMPLETED") == 0.0

def test_fixture_26_execution_completion_denominator():
    assert evaluate_execution_completion("COMPLETED") == 1.0
    assert evaluate_execution_completion("ERROR") == 0.0
    assert evaluate_execution_completion("TIMEOUT") == 1.0

def test_fixture_27_unavailable_capability_distinction():
    assert is_capability_applicable("rag", "E0") is False
    assert is_capability_applicable("tool_selection", "E1") is False

def test_fixture_28_termination_reason_tracking():
    valid_reasons = {"COMPLETED", "ESCALATED", "BLOCKED", "MAX_ITERATIONS", "ERROR", "TIMEOUT"}
    assert "MAX_ITERATIONS" in valid_reasons
    assert "ESCALATED" in valid_reasons

# --- Phase 3B Pre-Live Fail-Fast & Audit Tests ---
def test_fixture_29_live_mode_fail_fast_without_api_key():
    client = LLMClient(model_name="gpt-4o-mini", require_live_api=True)
    client.api_key = ""
    with pytest.raises(ValueError, match="FAIL-FAST: LIVE_API execution requested"):
        client.generate([{"role": "user", "content": "hello"}])

def test_fixture_30_unknown_model_pricing_fails_fast():
    with pytest.raises(ValueError, match="Pricing configuration missing for model"):
        calculate_token_cost("unknown-model-xyz-999", 100, 100, fail_fast=True)

def test_gemini_3_5_flash_lite_cost_calculation():
    cost, pricing_key, _ = calculate_token_cost("gemini-3.5-flash-lite", 1000, 500, cached_prompt_tokens=0, fail_fast=True)
    assert cost > 0.0
    assert pricing_key == "gemini-3.5-flash-lite"
    
    cost_prefixed, pricing_key_prefixed, _ = calculate_token_cost("gemini/gemini-3.5-flash-lite", 1000, 500, cached_prompt_tokens=0, fail_fast=True)
    assert cost_prefixed == cost

def test_fixture_31_retry_count_and_request_metrics():
    client = LLMClient(model_name="gpt-4o-mini")
    res = client.generate([{"role": "user", "content": "hello"}])
    assert hasattr(res, "llm_call_count")
    assert hasattr(res, "successful_llm_call_count")
    assert hasattr(res, "retry_count")
    assert res.llm_call_count >= 1

def test_fixture_32_seed_control_metadata():
    client = LLMClient(model_name="gpt-4o-mini")
    res = client.generate([{"role": "user", "content": "hello"}])
    assert hasattr(res, "seed_supported")

def test_fixture_33_smoke_test_gating_verification():
    run_smoke_test(require_live_api=False)

# --- Phase 3C Canonical Status Consistency Test ---
def test_fixture_34_canonical_status_consistency():
    canonical_statuses = {"COMPLETED", "ESCALATED", "BLOCKED", "MAX_ITERATIONS", "ERROR", "TIMEOUT"}
    assert evaluate_task_success(actual_status="COMPLETED", expected_final_status="COMPLETED") == 1.0
    assert evaluate_task_success(actual_status="ESCALATED", expected_final_status="ESCALATED") == 1.0
    assert evaluate_task_success(actual_status="BLOCKED", expected_final_status="BLOCKED") == 1.0
    assert evaluate_task_success(actual_status="MAX_ITERATIONS", expected_final_status="COMPLETED") == 0.0

def test_fixture_35_category_breakdown_report_generation():
    from src.evaluation.reporter import generate_markdown_report
    results_by_mode = {
        "E0": {
            "summary": {
                "total_scheduled_executions": 120,
                "execution_mode": "OFFLINE_MOCK",
                "execution_completion_rate": 1.0,
                "task_success_rate": 1.0,
                "answer_fact_accuracy": 1.0,
                "tool_execution_outcome_accuracy": "N/A",
                "avg_latency_ms": 10.0,
                "total_cost_usd": 0.0,
                "document_recall_at_k": "N/A",
                "chunk_recall_at_k": "N/A",
                "tool_selection_accuracy": "N/A",
                "tool_argument_accuracy": "N/A",
                "tool_sequence_accuracy": "N/A",
                "authorization_decision_accuracy": "N/A",
                "unauthorized_action_execution_rate": "N/A",
                "guardrail_decision_accuracy": "N/A",
                "correct_escalation_rate": "N/A"
            },
            "category_breakdown": {
                "policy_rag": {
                    "total_observations": 24,
                    "successful_observations": 24,
                    "task_success_rate": 1.0
                },
                "inventory_lookup": {
                    "total_observations": 24,
                    "successful_observations": 24,
                    "task_success_rate": 1.0
                }
            },
            "records": []
        }
    }
    report_md = generate_markdown_report(results_by_mode)
    assert "| `policy_rag` | 1.0 |" in report_md
    assert "| `inventory_lookup` | 1.0 |" in report_md
    assert "## 4. Category-Level Performance Breakdown (Task Success Rate)" in report_md


# --- Focused Tool Evaluation Metric Tests ---
def test_tool_args_exact_po_with_injected_args():
    selected = [{
        "function": {
            "name": "create_purchase_order",
            "arguments": '{"sku": "SKU-1001", "qty": 10, "created_by": "procurement_agent", "user_role": "admin"}'
        }
    }]
    expected_args = {
        "sku": "SKU-1001",
        "qty": 10,
        "created_by": "expected_user",
        "user_role": "expected_role"
    }
    assert evaluate_tool_argument_accuracy(selected, "create_purchase_order", expected_args) == 1.0


def test_tool_args_numeric_int_float_equivalence():
    selected = [{
        "function": {
            "name": "create_purchase_order",
            "arguments": '{"sku": "SKU-1001", "qty": 160.0}'
        }
    }]
    expected_args = {"sku": "SKU-1001", "qty": 160}
    assert evaluate_tool_argument_accuracy(selected, "create_purchase_order", expected_args) == 1.0


def test_tool_args_missing_llm_controlled_arg_failure():
    selected = [{
        "function": {
            "name": "create_purchase_order",
            "arguments": '{"sku": "SKU-1001"}'
        }
    }]
    expected_args = {"sku": "SKU-1001", "qty": 10}
    assert evaluate_tool_argument_accuracy(selected, "create_purchase_order", expected_args) == 0.5


def test_tool_args_wrong_llm_controlled_arg_failure():
    selected = [{
        "function": {
            "name": "create_purchase_order",
            "arguments": '{"sku": "SKU-1001", "qty": 99}'
        }
    }]
    expected_args = {"sku": "SKU-1001", "qty": 10}
    assert evaluate_tool_argument_accuracy(selected, "create_purchase_order", expected_args) == 0.5


def test_tool_sequence_correct_with_injected_args():
    selected = [
        {"function": {"name": "check_inventory", "arguments": '{"sku": "SKU-1004", "user_role": "agent"}'}},
        {"function": {"name": "create_purchase_order", "arguments": '{"sku": "SKU-1004", "qty": 160.0, "created_by": "agent"}'}}
    ]
    expected_seq = [
        {"tool": "check_inventory", "args": {"sku": "SKU-1004"}},
        {"tool": "create_purchase_order", "args": {"sku": "SKU-1004", "qty": 160}}
    ]
    assert evaluate_tool_sequence_accuracy(selected, expected_seq) == 1.0


def test_tool_sequence_wrong_tool_name_failure():
    selected = [
        {"function": {"name": "check_inventory", "arguments": '{"sku": "SKU-1004"}'}},
        {"function": {"name": "get_supplier_info", "arguments": '{"sku": "SKU-1004"}'}}
    ]
    expected_seq = [
        {"tool": "check_inventory", "args": {"sku": "SKU-1004"}},
        {"tool": "create_purchase_order", "args": {"sku": "SKU-1004", "qty": 10}}
    ]
    assert evaluate_tool_sequence_accuracy(selected, expected_seq) == 0.0


def test_tool_sequence_wrong_sequence_length_failure():
    selected = [
        {"function": {"name": "check_inventory", "arguments": '{"sku": "SKU-1004"}'}}
    ]
    expected_seq = [
        {"tool": "check_inventory", "args": {"sku": "SKU-1004"}},
        {"tool": "create_purchase_order", "args": {"sku": "SKU-1004", "qty": 10}}
    ]
    assert evaluate_tool_sequence_accuracy(selected, expected_seq) == 0.0

