import os
import sys
import json
import time
import random
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure project root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

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
from src.evaluation.reporter import save_benchmark_outputs
from src.observability import logger

def parse_args():
    parser = argparse.ArgumentParser(description="Run 480 Case-Execution Benchmark (3 Repetitions x 160 Executions)")
    parser.add_argument("--repetitions", type=int, default=3, help="Number of complete dataset repetitions (default: 3)")
    parser.add_argument("--seed", type=int, default=2026, help="Random seed for reproducible case shuffling")
    parser.add_argument("--dataset", type=str, default="data/eval_dataset.json", help="Path to evaluation dataset")
    parser.add_argument("--output-dir", type=str, default="experiments/outputs", help="Directory for results and traces")
    parser.add_argument("--offline", action="store_true", help="Run benchmark in OFFLINE_MOCK mode for offline verification")
    return parser.parse_args()

def run_live_benchmark():
    args = parse_args()
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"[-] Error: Evaluation dataset not found at {dataset_path}")
        sys.exit(1)

    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    modes = ["E0", "E1", "E2", "E3"]
    total_scheduled_executions = len(dataset) * len(modes) * args.repetitions

    print(f"=== Initializing Live Experimental Benchmark ===")
    print(f"[*] Total Scheduled Case Executions: {total_scheduled_executions} ({len(dataset)} cases x 4 modes x {args.repetitions} repetitions)")
    print(f"[*] Benchmark Random Seed: {args.seed}")

    orchestrator = AgentOrchestrator(require_live_api=not args.offline)
    print(f"[*] Execution Mode: {orchestrator.execution_mode}")

    trace_dir = Path(args.output_dir) / "trace_logs"
    trace_dir.mkdir(parents=True, exist_ok=True)

    all_case_execution_records = []
    results_by_mode: Dict[str, Any] = {m: {"records": [], "summary": {}} for m in modes}

    execution_counter = 0

    for rep in range(args.repetitions):
        rep_seed = args.seed + rep
        print(f"\n--- Starting Repetition {rep + 1}/{args.repetitions} (Random Seed: {rep_seed}) ---")
        
        # Shuffle dataset order per repetition for unbiased execution
        rng = random.Random(rep_seed)
        shuffled_dataset = list(dataset)
        rng.shuffle(shuffled_dataset)

        for item in shuffled_dataset:
            query = item["query"]
            user_role = item.get("user_role", "procurement_agent")

            for mode in modes:
                execution_counter += 1
                case_id = item["case_id"]

                # 1.0s operational delay between calls for rate-limit protection
                time.sleep(1.0)

                state = orchestrator.run(query=query, experiment_mode=mode, user_role=user_role)
                
                # Denominator semantics: Task Success uses ALL scheduled case executions
                exec_comp = evaluate_execution_completion(state["status"])
                task_succ = evaluate_task_success(state["status"], item.get("expected_final_status", "COMPLETED"))
                fact_acc = evaluate_answer_fact_accuracy(state, item.get("expected_answer_facts", {}))

                # Distinguish N/A from UNAVAILABLE
                if not is_capability_applicable("rag", mode):
                    doc_recall, chunk_recall = "N/A", "N/A"
                elif state["status"] == "ERROR":
                    doc_recall, chunk_recall = "UNAVAILABLE", "UNAVAILABLE"
                else:
                    doc_recall = evaluate_rag_recall(state.get("retrieved_doc_ids", []), item.get("expected_doc_ids", []))
                    chunk_recall = evaluate_rag_recall(state.get("retrieved_chunk_ids", []), item.get("expected_chunk_ids", []))

                if not is_capability_applicable("tool_selection", mode):
                    tool_sel_acc, tool_arg_acc, tool_seq_acc, tool_exec_acc = "N/A", "N/A", "N/A", "N/A"
                elif state["status"] == "ERROR":
                    tool_sel_acc, tool_arg_acc, tool_seq_acc, tool_exec_acc = "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE"
                else:
                    tool_sel_acc = evaluate_tool_selection_accuracy(state.get("selected_tool_calls", []), item.get("expected_tool"))
                    tool_arg_acc = evaluate_tool_argument_accuracy(state.get("selected_tool_calls", []), item.get("expected_tool"), item.get("expected_tool_args", {}))
                    tool_seq_acc = evaluate_tool_sequence_accuracy(state.get("selected_tool_calls", []), item.get("expected_tool_sequence", []))
                    tool_exec_acc = evaluate_tool_execution_outcome_accuracy(state, item.get("expected_tool_execution", "NOT_APPLICABLE"))

                if not is_capability_applicable("authorization_decision", mode):
                    auth_acc, guardrail_acc, escalation_acc = "N/A", "N/A", "N/A"
                elif state["status"] == "ERROR":
                    auth_acc, guardrail_acc, escalation_acc = "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE"
                else:
                    auth_acc = evaluate_authorization_decision_accuracy(state, item.get("expected_tool_execution", "NOT_APPLICABLE"), item.get("expected_escalation", False))
                    guardrail_acc = evaluate_guardrail_decision_accuracy(state, item.get("expected_tool_execution", "NOT_APPLICABLE"))
                    escalation_acc = evaluate_correct_escalation_rate(state.get("escalation_triggered", False), item.get("expected_escalation", False))

                unauth_exec_rate = evaluate_unauthorized_action_execution_rate(state, item.get("expected_tool_execution", "NOT_APPLICABLE"), mode) if is_capability_applicable("unauthorized_execution_rate", mode) else "N/A"

                record = {
                    "execution_id": f"EXEC-{execution_counter:04d}",
                    "repetition": rep + 1,
                    "case_id": case_id,
                    "category": item["category"],
                    "experiment_mode": mode,
                    "execution_mode": state.get("execution_mode", "OFFLINE_MOCK"),
                    "actual_status": state["status"],
                    "termination_reason": state.get("termination_reason", "COMPLETED"),
                    "agent_iteration_count": state.get("agent_iteration_count", 1),
                    "llm_call_count": state.get("llm_call_count", 0),
                    "tool_call_count": state.get("tool_call_count", 0),
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
                        "estimated_cost_usd": state["metrics"].get("estimated_cost_usd", 0.0)
                    }
                }

                results_by_mode[mode]["records"].append(record)
                all_case_execution_records.append(record)

                # Save raw trace file
                trace_file = trace_dir / f"{record['execution_id']}_{case_id}_{mode}.json"
                with open(trace_file, "w", encoding="utf-8") as f:
                    json.dump(record, f, indent=2)

    # Dynamic dataset categories
    dataset_categories = list(dict.fromkeys([item["category"] for item in dataset]))

    # Compute mode summaries over all case execution observations per mode
    for mode in modes:
        records = results_by_mode[mode]["records"]
        n_obs = len(records)
        
        def calc_avg(metric_name):
            vals = [r["metrics"][metric_name] for r in records if isinstance(r["metrics"][metric_name], (int, float))]
            return round(sum(vals) / len(vals), 3) if vals else "N/A"

        def calc_p95(metric_name):
            vals = sorted([r["metrics"][metric_name] for r in records if isinstance(r["metrics"][metric_name], (int, float))])
            if not vals:
                return "N/A"
            idx = int(0.95 * len(vals))
            return round(vals[min(idx, len(vals) - 1)], 2)

        results_by_mode[mode]["summary"] = {
            "total_scheduled_executions": n_obs,
            "execution_mode": records[0]["execution_mode"] if records else "OFFLINE_MOCK",
            "execution_completion_rate": round(sum(r["metrics"]["execution_completion_rate"] for r in records) / n_obs, 3),
            "task_success_rate": round(sum(r["metrics"]["task_success_rate"] for r in records) / n_obs, 3),
            "answer_fact_accuracy": calc_avg("answer_fact_accuracy"),
            "document_recall_at_k": calc_avg("document_recall_at_k"),
            "chunk_recall_at_k": calc_avg("chunk_recall_at_k"),
            "tool_selection_accuracy": calc_avg("tool_selection_accuracy"),
            "tool_argument_accuracy": calc_avg("tool_argument_accuracy"),
            "tool_sequence_accuracy": calc_avg("tool_sequence_accuracy"),
            "tool_execution_outcome_accuracy": calc_avg("tool_execution_outcome_accuracy"),
            "authorization_decision_accuracy": calc_avg("authorization_decision_accuracy"),
            "unauthorized_action_execution_rate": calc_avg("unauthorized_action_execution_rate"),
            "guardrail_decision_accuracy": calc_avg("guardrail_decision_accuracy"),
            "correct_escalation_rate": calc_avg("correct_escalation_rate"),
            "avg_latency_ms": calc_avg("latency_ms"),
            "p95_latency_ms": calc_p95("latency_ms"),
            "total_cost_usd": round(sum(r["metrics"]["estimated_cost_usd"] for r in records), 6)
        }

        category_breakdown = {}
        for cat in dataset_categories:
            cat_records = [r for r in records if r["category"] == cat]
            total_cat_obs = len(cat_records)
            succ_vals = [r["metrics"]["task_success_rate"] for r in cat_records if isinstance(r["metrics"]["task_success_rate"], (int, float))]
            succ_count = sum(succ_vals)
            task_succ_rate = round(succ_count / total_cat_obs, 3) if total_cat_obs > 0 else "N/A"
            category_breakdown[cat] = {
                "total_observations": total_cat_obs,
                "successful_observations": int(succ_count) if isinstance(succ_count, (int, float)) and float(succ_count).is_integer() else succ_count,
                "task_success_rate": task_succ_rate
            }

        results_by_mode[mode]["category_breakdown"] = category_breakdown

    save_benchmark_outputs(results_by_mode, output_dir=args.output_dir)
    print(f"\n[+] Live benchmark completed {total_scheduled_executions} case executions successfully!")

if __name__ == "__main__":
    run_live_benchmark()
