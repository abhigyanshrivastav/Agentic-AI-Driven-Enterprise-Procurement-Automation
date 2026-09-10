import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from src.api.schemas import QueryRequestDTO, QueryResponseDTO, ExecutionMetricsDTO, ExperimentRunRequestDTO
from src.agent.graph import AgentOrchestrator
from src.evaluation.runner import BenchmarkRunner
from src.evaluation.reporter import save_benchmark_outputs
from src.observability import logger

router = APIRouter()
orchestrator = AgentOrchestrator()

@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Enterprise Procurement LLMOps Gateway"}

@router.post("/query", response_model=QueryResponseDTO)
async def process_query(request: QueryRequestDTO):
    try:
        # Run orchestrator graph inside threadpool to prevent blocking the async event loop
        orchestrator = AgentOrchestrator()
        state = await asyncio.to_thread(
            orchestrator.run,
            query=request.query,
            experiment_mode=request.experiment_mode,
            user_role=request.user_role,
            trace_id=request.trace_id
        )

        metrics_dto = ExecutionMetricsDTO(
            latency_ms=state["metrics"].get("latency_ms", 0.0),
            prompt_tokens=state["metrics"].get("prompt_tokens", 0),
            completion_tokens=state["metrics"].get("completion_tokens", 0),
            estimated_cost_usd=state["metrics"].get("estimated_cost_usd", 0.0),
            tool_calls_count=state["metrics"].get("tool_calls_count", 0)
        )

        return QueryResponseDTO(
            trace_id=state["trace_id"],
            experiment_mode=state["experiment_mode"],
            user_role=state["user_role"],
            answer=state["final_response"],
            status=state["status"],
            escalation_triggered=state.get("escalation_triggered", False),
            escalation_reason=state.get("escalation_reason"),
            metrics=metrics_dto
        )
    except Exception as e:
        logger.error(f"Error processing API query: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal execution error: {str(e)}")

@router.post("/experiment/run")
async def run_experiment_benchmark(request: ExperimentRunRequestDTO, background_tasks: BackgroundTasks):
    try:
        runner = BenchmarkRunner()
        results = await asyncio.to_thread(runner.run_benchmark, modes=request.modes)
        background_tasks.add_task(save_benchmark_outputs, results)
        return {
            "status": "SUCCESS",
            "message": f"Successfully executed benchmark over modes {request.modes}",
            "modes_evaluated": list(results.keys()),
            "results_summary": {m: results[m]["summary"] for m in results}
        }
    except Exception as e:
        logger.error(f"Error running benchmark via API: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Benchmark failure: {str(e)}")
