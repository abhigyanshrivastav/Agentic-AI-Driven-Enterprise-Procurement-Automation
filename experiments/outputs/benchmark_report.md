# Experimental Benchmark Results (E0–E3)

> [!NOTE]
> **SYSTEM EXECUTION MODE**: `OFFLINE_MOCK`

## 1. Summary Performance Comparison

| Mode | Runs | Completion Rate | Task Success Rate | Fact Accuracy | Tool Exec Acc | Latency (ms) | Total Cost ($) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **E0** | 120 | 1.0 | **0.875** | 0.05 | N/A | 2.814 | $0.001884 |
| **E1** | 120 | 1.0 | **0.875** | 0.05 | N/A | 10.534 | $0.005775 |
| **E2** | 120 | 0.975 | **0.875** | 0.197 | 0.667 | 17.763 | $0.010575 |
| **E3** | 120 | 1.0 | **0.925** | 0.195 | 0.7 | 17.28 | $0.010572 |

## 2. RAG & Tool Capability Metrics

| Mode | Doc Recall@k | Chunk Recall@k | Tool Selection Acc | Tool Arg Acc | Tool Sequence Acc |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **E0** | N/A | N/A | N/A | N/A | N/A |
| **E1** | 1.0 | 0.625 | N/A | N/A | N/A |
| **E2** | 1.0 | 0.625 | 0.59 | 0.233 | 0.0 |
| **E3** | 1.0 | 0.625 | 0.625 | 0.258 | 0.065 |

## 3. Safety & Governance Control Metrics

| Mode | Auth Decision Acc | Unauthorized Action Exec Rate | Guardrail Acc | Escalation Acc |
| :--- | :---: | :---: | :---: | :---: |
| **E0** | N/A | **N/A** | N/A | N/A |
| **E1** | N/A | **N/A** | N/A | N/A |
| **E2** | N/A | **1.0** | N/A | N/A |
| **E3** | 0.975 | **0.0** | 1.0 | 0.975 |

## 4. Category-Level Performance Breakdown (Task Success Rate)

| Category | **E0** | **E1** | **E2** | **E3** |
| :--- | :---: | :---: | :---: | :---: |
| `policy_rag` | 1.0 | 1.0 | 1.0 | 1.0 |
| `inventory_lookup` | 1.0 | 1.0 | 1.0 | 1.0 |
| `supplier_lookup` | 1.0 | 1.0 | 1.0 | 1.0 |
| `po_execution` | 1.0 | 1.0 | 1.0 | 0.875 |
| `authorization_action` | 0.75 | 0.75 | 0.75 | 1.0 |
| `adversarial_edge` | 0.0 | 0.0 | 0.0 | 0.5 |

## Architectural Observations

- **Answer Fact Accuracy Note**: Answer Fact Accuracy measures the proportion of ground-truth fields that can be deterministically extracted and correctly matched from system outputs.
- **Safety Control Note**: E2 lacks authorization guardrails, resulting in unauthorized tool execution on policy boundary cases. E3 halts unauthorized actions deterministically.