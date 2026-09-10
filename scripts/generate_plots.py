import json
from pathlib import Path

import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_PATH = BASE_DIR / "experiments" / "outputs" / "benchmark_results.json"
PLOTS_DIR = BASE_DIR / "experiments" / "outputs" / "plots"


def numeric(value):
    """Return numeric value or None for N/A/null fields."""
    return value if isinstance(value, (int, float)) else None


def generate_benchmark_plots():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    if not RESULTS_PATH.exists():
        print(
            f"[!] Benchmark results file not found: {RESULTS_PATH}\n"
            "[!] Run the benchmark runner first."
        )
        return

    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        results = json.load(f)

    modes = list(results.keys())

    # ------------------------------------------------------------------
    # Extract metrics from CURRENT benchmark schema
    # ------------------------------------------------------------------
    summaries = {
        mode: results[mode]["summary"]
        for mode in modes
    }

    avg_latencies = [
        numeric(summaries[m].get("avg_latency_ms")) or 0
        for m in modes
    ]

    p95_latencies = [
        numeric(summaries[m].get("p95_latency_ms")) or 0
        for m in modes
    ]

    avg_costs_milli_usd = [
        (
            summaries[m]["total_cost_usd"]
            / summaries[m]["total_scheduled_executions"]
        ) * 1000
        if summaries[m].get("total_scheduled_executions", 0) > 0
        else 0
        for m in modes
    ]

    fact_accuracies = [
        (numeric(summaries[m].get("answer_fact_accuracy")) or 0) * 100
        for m in modes
    ]

    task_success_rates = [
        (numeric(summaries[m].get("task_success_rate")) or 0) * 100
        for m in modes
    ]

    tool_execution_accuracies = [
        (numeric(summaries[m].get("tool_execution_outcome_accuracy")) or 0) * 100
        for m in modes
    ]

    # ------------------------------------------------------------------
    # Plot 1: Average vs P95 Latency
    # ------------------------------------------------------------------
    plt.figure(figsize=(8, 5))

    x = range(len(modes))
    width = 0.35

    plt.bar(
        [i - width / 2 for i in x],
        avg_latencies,
        width=width,
        label="Average Latency (ms)",
    )

    plt.bar(
        [i + width / 2 for i in x],
        p95_latencies,
        width=width,
        label="P95 Latency (ms)",
    )

    plt.xticks(x, modes)
    plt.xlabel("Experiment Configuration Mode")
    plt.ylabel("Latency (ms)")
    plt.title("E0-E3 Response Latency Comparison")
    plt.legend()
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()

    plot1_path = PLOTS_DIR / "latency_comparison.png"
    plt.savefig(plot1_path, dpi=300)
    plt.close()

    # ------------------------------------------------------------------
    # Plot 2: Fact Accuracy vs Average Cost
    # ------------------------------------------------------------------
    fig, ax1 = plt.subplots(figsize=(8, 5))

    ax2 = ax1.twinx()

    ax1.bar(
        modes,
        fact_accuracies,
        alpha=0.7,
        width=0.4,
        label="Answer Fact Accuracy (%)",
    )

    ax2.plot(
        modes,
        avg_costs_milli_usd,
        marker="o",
        linewidth=2.5,
        label="Average Cost (milli-USD)",
    )

    ax1.set_xlabel("Experiment Configuration Mode")
    ax1.set_ylabel("Answer Fact Accuracy (%)")
    ax2.set_ylabel("Average Cost per Execution (milli-USD)")

    plt.title("E0-E3 Accuracy vs Execution Cost Trade-Off")

    fig.tight_layout()

    plot2_path = PLOTS_DIR / "cost_vs_accuracy.png"
    plt.savefig(plot2_path, dpi=300)
    plt.close()

    # ------------------------------------------------------------------
    # Plot 3: Task Success Rate
    # ------------------------------------------------------------------
    plt.figure(figsize=(8, 5))

    plt.bar(
        modes,
        task_success_rates,
        width=0.55,
    )

    plt.xlabel("Experiment Configuration Mode")
    plt.ylabel("Task Success Rate (%)")
    plt.ylim(0, 100)
    plt.title("E0-E3 Task Success Rate")
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()

    plot3_path = PLOTS_DIR / "task_success_rate.png"
    plt.savefig(plot3_path, dpi=300)
    plt.close()

    # ------------------------------------------------------------------
    # Plot 4: Tool Execution Outcome Accuracy
    # ------------------------------------------------------------------
    # E0/E1 are not applicable, so display them as zero only for
    # visualization. The underlying benchmark data remains N/A.
    plt.figure(figsize=(8, 5))

    plt.bar(
        modes,
        tool_execution_accuracies,
        width=0.55,
    )

    plt.xlabel("Experiment Configuration Mode")
    plt.ylabel("Tool Execution Outcome Accuracy (%)")
    plt.ylim(0, 100)
    plt.title("E2-E3 Tool Execution Outcome Accuracy")
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()

    plot4_path = PLOTS_DIR / "tool_execution_accuracy.png"
    plt.savefig(plot4_path, dpi=300)
    plt.close()

    print("[+] Saved evaluation figures:")
    print(f"    {plot1_path}")
    print(f"    {plot2_path}")
    print(f"    {plot3_path}")
    print(f"    {plot4_path}")


if __name__ == "__main__":
    generate_benchmark_plots()