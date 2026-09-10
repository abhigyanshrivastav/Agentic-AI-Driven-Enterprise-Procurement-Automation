import json
from pathlib import Path
from typing import Dict, Any

def generate_markdown_report(results_by_mode: Dict[str, Any]) -> str:
    md = []
    md.append("# Experimental Benchmark Results (E0–E3)")
    
    # Execution Mode Banner
    exec_mode = "OFFLINE_MOCK"
    if results_by_mode:
        first_mode = next(iter(results_by_mode.values()))
        exec_mode = first_mode.get("summary", {}).get("execution_mode", "OFFLINE_MOCK")
        
    md.append(f"\n> [!NOTE]\n> **SYSTEM EXECUTION MODE**: `{exec_mode}`\n")

    # Table 1: Summary Performance Comparison
    md.append("## 1. Summary Performance Comparison\n")
    md.append("| Mode | Runs | Completion Rate | Task Success Rate | Fact Accuracy | Tool Exec Acc | Latency (ms) | Total Cost ($) |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    for mode, data in results_by_mode.items():
        s = data["summary"]
        md.append(
            f"| **{mode}** | {s['total_scheduled_executions']} | {s['execution_completion_rate']} | "
            f"**{s['task_success_rate']}** | {s['answer_fact_accuracy']} | "
            f"{s['tool_execution_outcome_accuracy']} | {s['avg_latency_ms']} | ${s['total_cost_usd']:.6f} |"
        )

    # Table 2: RAG & Tool Capabilities
    md.append("\n## 2. RAG & Tool Capability Metrics\n")
    md.append("| Mode | Doc Recall@k | Chunk Recall@k | Tool Selection Acc | Tool Arg Acc | Tool Sequence Acc |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: |")

    for mode, data in results_by_mode.items():
        s = data["summary"]
        md.append(
            f"| **{mode}** | {s['document_recall_at_k']} | {s['chunk_recall_at_k']} | "
            f"{s['tool_selection_accuracy']} | {s['tool_argument_accuracy']} | "
            f"{s['tool_sequence_accuracy']} |"
        )

    # Table 3: Safety & Governance Controls
    md.append("\n## 3. Safety & Governance Control Metrics\n")
    md.append("| Mode | Auth Decision Acc | Unauthorized Action Exec Rate | Guardrail Acc | Escalation Acc |")
    md.append("| :--- | :---: | :---: | :---: | :---: |")

    for mode, data in results_by_mode.items():
        s = data["summary"]
        md.append(
            f"| **{mode}** | {s['authorization_decision_accuracy']} | "
            f"**{s['unauthorized_action_execution_rate']}** | "
            f"{s['guardrail_decision_accuracy']} | {s['correct_escalation_rate']} |"
        )

    # Table 4: Category Breakdown
    md.append("\n## 4. Category-Level Performance Breakdown (Task Success Rate)\n")
    all_cats = []
    for mode, data in results_by_mode.items():
        for cat in data.get("category_breakdown", {}).keys():
            if cat not in all_cats:
                all_cats.append(cat)
    categories = all_cats if all_cats else ["policy_rag", "inventory_lookup", "supplier_lookup", "po_execution", "authorization_action", "adversarial_edge"]
    
    header = "| Category | " + " | ".join([f"**{m}**" for m in results_by_mode.keys()]) + " |"
    divider = "| :--- | " + " | ".join([":---:" for _ in results_by_mode.keys()]) + " |"
    md.append(header)
    md.append(divider)

    for cat in categories:
        row = [f"`{cat}`"]
        for mode, data in results_by_mode.items():
            cat_data = data.get("category_breakdown", {}).get(cat, {})
            succ = cat_data.get("task_success_rate", "N/A")
            row.append(str(succ))
        md.append("| " + " | ".join(row) + " |")

    md.append("\n## Architectural Observations\n")
    md.append("- **Answer Fact Accuracy Note**: Answer Fact Accuracy measures the proportion of ground-truth fields that can be deterministically extracted and correctly matched from system outputs.")
    md.append("- **Safety Control Note**: E2 lacks authorization guardrails, resulting in unauthorized tool execution on policy boundary cases. E3 halts unauthorized actions deterministically.")

    return "\n".join(md)

def save_benchmark_outputs(results_by_mode: Dict[str, Any], output_dir: str = "experiments/outputs"):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    json_file = out_path / "benchmark_results.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(results_by_mode, f, indent=2)

    md_file = out_path / "benchmark_report.md"
    report_md = generate_markdown_report(results_by_mode)
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"[+] Saved benchmark report to {md_file} and {json_file}")
