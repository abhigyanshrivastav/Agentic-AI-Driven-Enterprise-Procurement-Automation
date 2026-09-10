import time
import uuid
from typing import Dict, Any, List, Optional
from src.observability.logger import logger

class SpanContext:
    def __init__(self, tracer: 'ExecutionTracer', trace_id: str, span_name: str, metadata: Optional[Dict[str, Any]] = None):
        self.tracer = tracer
        self.trace_id = trace_id
        self.span_name = span_name
        self.span_id = f"SP-{uuid.uuid4().hex[:6].upper()}"
        self.metadata = metadata or {}
        self.start_time = 0.0

    def __enter__(self):
        self.start_time = time.time()
        logger.info(
            f"Span started: {self.span_name}",
            extra={"trace_id": self.trace_id, "span_id": self.span_id, "payload": self.metadata}
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000.0
        status = "ERROR" if exc_type else "SUCCESS"
        self.tracer.record_span(self.trace_id, {
            "span_id": self.span_id,
            "span_name": self.span_name,
            "duration_ms": round(duration_ms, 2),
            "status": status,
            "metadata": self.metadata
        })
        logger.info(
            f"Span finished: {self.span_name} ({duration_ms:.2f}ms)",
            extra={"trace_id": self.trace_id, "span_id": self.span_id, "payload": {"duration_ms": duration_ms, "status": status}}
        )

class ExecutionTracer:
    """Lightweight in-memory execution span tracer for LLMOps observability."""

    def __init__(self):
        self.spans: Dict[str, List[Dict[str, Any]]] = {}

    def start_span(self, trace_id: str, span_name: str, metadata: Optional[Dict[str, Any]] = None) -> SpanContext:
        return SpanContext(self, trace_id, span_name, metadata)

    def record_span(self, trace_id: str, span_data: Dict[str, Any]):
        if trace_id not in self.spans:
            self.spans[trace_id] = []
        self.spans[trace_id].append(span_data)

    def get_trace_spans(self, trace_id: str) -> List[Dict[str, Any]]:
        return self.spans.get(trace_id, [])

tracer = ExecutionTracer()
