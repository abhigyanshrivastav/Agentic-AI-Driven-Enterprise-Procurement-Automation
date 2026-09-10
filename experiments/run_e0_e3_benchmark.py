import os
import sys
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation.runner import BenchmarkRunner
from src.evaluation.reporter import save_benchmark_outputs

def main():
    print("===============================================================")
    print("   LLMOps Experimental Prototype — E0–E3 Benchmark Execution  ")
    print("===============================================================")

    runner = BenchmarkRunner(dataset_path="data/eval_dataset.json")
    modes = ["E0", "E1", "E2", "E3"]
    
    print(f"[*] Executing benchmark over modes: {modes}...")
    results = runner.run_benchmark(modes=modes)
    
    save_benchmark_outputs(results, output_dir="experiments/outputs")
    print("[+] Benchmark execution successfully completed!")

if __name__ == "__main__":
    main()
