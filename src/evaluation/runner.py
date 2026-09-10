import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from src.agent.graph import AgentOrchestrator
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
    is_capability_applicable
)
from src.observability import logger

def safe_avg(values: List[Optional[float]]) -> Union[str, float]:
    valid = [v for v in values if v is not None]
    if not valid:
        return "N/A"
    return round(sum(valid) / len(valid), 3)

class BenchmarkRunner:
    """Runs batch evaluation of E0-E3 configurations over eval dataset."""

    def __init__(self, dataset_path: str = "data/eval_dataset.json"):
        self.dataset_path = Path(dataset_path)
        self.orchestrator = AgentOrchestrator()
        self.dataset: List[Dict[str, Any]] = []
        self._load_dataset()

    def _load_dataset(self):
        if self.dataset_path.exists():
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                self.dataset = json.load(f)

    def run_benchmark(self, modes: List[str] = ["E0", "E1", "E2", "E3"]) -> Dict[str, Any]:
        if not self.dataset:
            logger.error(f"Evaluation dataset missing at {self.dataset_path}")
            return {}

        results_by_mode: Dict[str, Any] = {}

        for mode in modes:
            logger.info(f"=== Starting Benchmark Evaluation for Mode: {mode} ===")
            records = []

            for item in self.dataset:
                query = item["query"]
                user_role = item.get("user_role", "procurement_agent")

                state = self.orchestrator.run(query=query, experiment_mode=mode, user_role=user_role)
                
                # Universal Metrics
                exec_comp = evaluate_execution_completion(state["status"])
                task_succ = evaluate_task_success(state["status"], item.get("expected_final_status", "COMPLETED"))
                fact_acc = evaluate_answer_fact_accuracy(state, item.get("expected_answer_facts", {}))

                # RAG Metrics (Masked if capability not applicable to mode or item has no expected docs/chunks)
                doc_recall = evaluate_rag_recall(state.get("retrieved_doc_ids", []), item.get("expected_doc_ids", [])) if is_capability_applicable("rag", mode) else None
                chunk_recall = evaluate_rag_recall(state.get("retrieved_chunk_ids", []), item.get("expected_chunk_ids", [])) if is_capability_applicable("rag", mode) else None

                # Tool Metrics (Masked if capability not applicable to mode)
                tool_sel_acc = evaluate_tool_selection_accuracy(state.get("selected_tool_calls", []), item.get("expected_tool")) if is_capability_applicable("tool_selection", mode) else None
                tool_arg_acc = evaluate_tool_argument_accuracy(state.get("selected_tool_calls", []), item.get("expected_tool"), item.get("expected_tool_args", {})) if is_capability_applicable("tool_args", mode) else None
                tool_seq_acc = evaluate_tool_sequence_accuracy(state.get("selected_tool_calls", []), item.get("expected_tool_sequence", [])) if is_capability_applicable("tool_sequence", mode) else None
                tool_exec_acc = evaluate_tool_execution_outcome_accuracy(state, item.get("expected_tool_execution", "NOT_APPLICABLE")) if is_capability_applicable("tool_execution", mode) else None

                # Safety & Control Metrics
                auth_acc = evaluate_authorization_decision_accuracy(state, item.get("expected_tool_execution", "NOT_APPLICABLE"), item.get("expected_escalation", False)) if is_capability_applicable("authorization_decision", mode) else None
                unauth_exec_rate = evaluate_unauthorized_action_execution_rate(state, item.get("expected_tool_execution", "NOT_APPLICABLE"), mode) if is_capability_applicable("unauthorized_execution_rate", mode) else None
                guardrail_acc = evaluate_guardrail_decision_accuracy(state, item.get("expected_tool_execution", "NOT_APPLICABLE")) if is_capability_applicable("guardrail_decision", mode) else None
                escalation_acc = evaluate_correct_escalation_rate(state.get("escalation_triggered", False), item.get("expected_escalation", False)) if is_capability_applicable("correct_escalation", mode) else None

                record = {
                    "case_id": item["case_id"],
                    "category": item["category"],
                    "query": query,
                    "experiment_mode": mode,
                    "execution_mode": state.get("execution_mode", "OFFLINE_MOCK"),
                    "actual_status": state["status"],
                    "expected_final_status": item.get("expected_final_status", "COMPLETED"),
                    "final_response": state["final_response"],
                    
                    "metrics": {
                        "execution_completion_rate": exec_comp,
                        "task_success_rate": task_succ,
                        "answer_fact_accuracy": fact_acc,
                        "document_recall_at_k": doc_recall,
                        "chunk_recall_at_k": chunk_recall,
                        "tool_selection_accuracy": tool_sel_acc,
                        "tool_argument_accuracy": tool_arg_acc,
                        "tool_sequence_accuracy": tool_seq_acc,
                        "tool_execution_outcome_accuracy": tool_exec_acc,
                        "authorization_decision_accuracy": auth_acc,
                        "unauthorized_action_execution_rate": unauth_exec_rate,
                        "guardrail_decision_accuracy": guardrail_acc,
                        "correct_escalation_rate": escalation_acc,
                        "latency_ms": state["metrics"].get("latency_ms", 0.0),
                        "prompt_tokens": state["metrics"].get("prompt_tokens", 0),
                        "completion_tokens": state["metrics"].get("completion_tokens", 0),
                        "estimated_cost_usd": state["metrics"].get("estimated_cost_usd", 0.0),
                        "tool_calls_count": state["metrics"].get("tool_calls_count", 0)
                    }
                }
                records.append(record)

            # Aggregate Summary across all queries in mode
            summary = {
                "total_runs": len(records),
                "execution_mode": records[0]["execution_mode"] if records else "OFFLINE_MOCK",
                "execution_completion_rate": safe_avg([r["metrics"]["execution_completion_rate"] for r in records]),
                "task_success_rate": safe_avg([r["metrics"]["task_success_rate"] for r in records]),
                "answer_fact_accuracy": safe_avg([r["metrics"]["answer_fact_accuracy"] for r in records]),
                "document_recall_at_k": safe_avg([r["metrics"]["document_recall_at_k"] for r in records]),
                "chunk_recall_at_k": safe_avg([r["metrics"]["chunk_recall_at_k"] for r in records]),
                "tool_selection_accuracy": safe_avg([r["metrics"]["tool_selection_accuracy"] for r in records]),
                "tool_argument_accuracy": safe_avg([r["metrics"]["tool_argument_accuracy"] for r in records]),
                "tool_sequence_accuracy": safe_avg([r["metrics"]["tool_sequence_accuracy"] for r in records]),
                "tool_execution_outcome_accuracy": safe_avg([r["metrics"]["tool_execution_outcome_accuracy"] for r in records]),
                "authorization_decision_accuracy": safe_avg([r["metrics"]["authorization_decision_accuracy"] for r in records]),
                "unauthorized_action_execution_rate": safe_avg([r["metrics"]["unauthorized_action_execution_rate"] for r in records]),
                "guardrail_decision_accuracy": safe_avg([r["metrics"]["guardrail_decision_accuracy"] for r in records]),
                "correct_escalation_rate": safe_avg([r["metrics"]["correct_escalation_rate"] for r in records]),
                "avg_latency_ms": safe_avg([r["metrics"]["latency_ms"] for r in records]),
                "total_cost_usd": round(sum(r["metrics"]["estimated_cost_usd"] for r in records), 6)
            }

            # Category-level breakdown aggregation
            category_breakdown = {}
            categories = list(dict.fromkeys([r["category"] for r in records]))
            for cat in categories:
                cat_records = [r for r in records if r["category"] == cat]
                category_breakdown[cat] = {
                    "count": len(cat_records),
                    "task_success_rate": safe_avg([r["metrics"]["task_success_rate"] for r in cat_records]),
                    "answer_fact_accuracy": safe_avg([r["metrics"]["answer_fact_accuracy"] for r in cat_records]),
                    "tool_execution_outcome_accuracy": safe_avg([r["metrics"]["tool_execution_outcome_accuracy"] for r in cat_records]),
                    "correct_escalation_rate": safe_avg([r["metrics"]["correct_escalation_rate"] for r in cat_records])
                }

            results_by_mode[mode] = {
                "summary": summary,
                "category_breakdown": category_breakdown,
                "records": records
            }

        return results_by_mode
