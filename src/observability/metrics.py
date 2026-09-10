from typing import Dict, Any, List
import numpy as np

class MetricsAggregator:
    """Aggregates latency, token usage, cost, and error rates across runs."""

    def __init__(self):
        self.records: List[Dict[str, Any]] = []

    def add_record(self, record: Dict[str, Any]):
        self.records.append(record)

    def compute_summary(self, mode_filter: str = None) -> Dict[str, Any]:
        filtered = [r for r in self.records if r.get("experiment_mode") == mode_filter] if mode_filter else self.records
        if not filtered:
            return {
                "total_runs": 0,
                "avg_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "total_cost_usd": 0.0,
                "avg_prompt_tokens": 0.0,
                "avg_completion_tokens": 0.0,
                "success_rate": 0.0,
                "escalation_rate": 0.0
            }

        latencies = [r.get("metrics", {}).get("latency_ms", 0.0) for r in filtered]
        costs = [r.get("metrics", {}).get("estimated_cost_usd", 0.0) for r in filtered]
        prompt_tokens = [r.get("metrics", {}).get("prompt_tokens", 0) for r in filtered]
        completion_tokens = [r.get("metrics", {}).get("completion_tokens", 0) for r in filtered]

        success_count = sum(1 for r in filtered if r.get("status") == "SUCCESS")
        escalated_count = sum(1 for r in filtered if r.get("status") == "ESCALATED" or r.get("escalation_triggered"))

        return {
            "total_runs": len(filtered),
            "avg_latency_ms": round(float(np.mean(latencies)), 2),
            "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
            "total_cost_usd": round(float(sum(costs)), 6),
            "avg_cost_per_query_usd": round(float(np.mean(costs)), 6),
            "avg_prompt_tokens": round(float(np.mean(prompt_tokens)), 1),
            "avg_completion_tokens": round(float(np.mean(completion_tokens)), 1),
            "success_rate": round(success_count / len(filtered), 3),
            "escalation_rate": round(escalated_count / len(filtered), 3)
        }
