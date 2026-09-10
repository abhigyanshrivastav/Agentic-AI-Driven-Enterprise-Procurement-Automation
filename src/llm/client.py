import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from src.config import get_settings, PRICING_VERSION, is_valid_api_key
from src.llm.cost import calculate_token_cost
from src.observability import logger

def _safe_int(val: Any, default: int = 0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

def _get_usage_attr(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)

class ProviderQuotaError(RuntimeError):
    """Raised when LLM provider returns insufficient_quota or 429 quota limit error."""
    pass

class LLMResponseDTO(BaseModel):
    content: str
    tool_calls: List[Dict[str, Any]] = []
    prompt_tokens: int = 0
    cached_prompt_tokens: int = 0
    uncached_prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    is_estimated_tokens: bool = False
    estimated_cost_usd: float = 0.0
    latency_ms: float = 0.0
    
    # Explicit Frozen Model & Provider Metadata
    provider: str = "openai"
    model_id: str = "gpt-4o-mini"
    model_snapshot: str = "2024-07-18"
    endpoint: str = "https://api.openai.com/v1"
    temperature: float = 0.0
    seed_requested: Optional[int] = 2026
    seed_supported: bool = False
    seed_applied: Optional[int] = None
    pricing_version: str = PRICING_VERSION
    pricing_model_key: str = "gpt-4o-mini"
    
    # Operational Request Audit Counters
    llm_call_count: int = 1
    successful_llm_call_count: int = 1
    retry_count: int = 0

class LLMClient:
    """LLM API client wrapper supporting live API calls with retry tracking, quota classification, and strict fail-fast mode."""

    def __init__(self, model_name: Optional[str] = None, require_live_api: Optional[bool] = None, force_mock: bool = False):
        settings = get_settings()
        self.provider = settings.llm_provider
        self.model_id = model_name or settings.llm_model
        self.model_snapshot = settings.model_snapshot
        self.endpoint = settings.api_endpoint if settings.llm_provider != "gemini" else "https://generativelanguage.googleapis.com/v1beta"
        self.api_key = settings.llm_api_key
        self.temperature = settings.temperature
        self.require_live_api = require_live_api
        self.force_mock = force_mock
        
        self.seed_requested = settings.seed_requested
        self.seed_supported = settings.seed_supported
        self.seed_applied = settings.seed_applied

    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 1000,
        seed: Optional[int] = None
    ) -> LLMResponseDTO:
        start_time = time.perf_counter()
        temp = temperature if temperature is not None else self.temperature
        target_seed = seed if seed is not None else self.seed_requested
        
        # 1. Fail-Fast Check if LIVE_API is explicitly required
        if self.require_live_api is True:
            if not is_valid_api_key(self.api_key):
                raise ValueError(
                    f"FAIL-FAST: LIVE_API execution requested for model '{self.model_id}', "
                    "but no valid API credential was found. Automatic fallback to mock is strictly prohibited in live benchmark mode."
                )

        # 2. Attempt Live API Call with Retry Instrumentation if API Key is Present and LIVE_API is required
        if is_valid_api_key(self.api_key) and not self.force_mock and self.require_live_api is True:
            max_retries = 3
            attempt_count = 0
            success_count = 0
            retry_count = 0
            last_exception = None

            for attempt in range(max_retries):
                attempt_count += 1
                if attempt > 0:
                    retry_count += 1
                    time.sleep(2.0 * (2 ** (attempt - 1)))

                try:
                    import litellm
                    
                    model_param = self.model_id
                    if (self.provider == "gemini" or model_param.startswith("gemini-")) and not model_param.startswith("gemini/"):
                        model_param = f"gemini/{model_param}"
                    elif not model_param.startswith("gemini/") and not model_param.startswith("openai/") and "/" not in model_param:
                        if self.provider:
                            model_param = f"{self.provider}/{model_param}"

                    kwargs = {
                        "model": model_param,
                        "messages": messages,
                        "temperature": temp,
                        "api_key": self.api_key
                    }
                    if self.provider == "gemini":
                        kwargs["gemini_api_key"] = self.api_key

                    if tools:
                        kwargs["tools"] = tools
                    # Do not send seed to Gemini unless explicitly required.
                    # Gemini/LiteLLM provider combinations may return incomplete
                    # metadata for seed-related fields.
                    actual_seed_applied = None

                    response = litellm.completion(**kwargs)
                    latency_ms = (time.perf_counter() - start_time) * 1000.0
                    success_count = 1
                    
                    choice = response.choices[0].message
                    content = choice.content or ""
                    
                    extracted_tool_calls = []
                    if hasattr(choice, "tool_calls") and choice.tool_calls:
                        for tc in choice.tool_calls:
                            args_val = tc.function.arguments
                            if not isinstance(args_val, str):
                                import json
                                args_val = json.dumps(args_val)
                            extracted_tool_calls.append({
                                "id": getattr(tc, "id", "call_01"),
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": args_val
                                }
                            })

                    usage = getattr(response, "usage", None)
                    if usage:
                        raw_prompt = _get_usage_attr(usage, "prompt_tokens")
                        raw_completion = _get_usage_attr(usage, "completion_tokens")
                        raw_total = _get_usage_attr(usage, "total_tokens")

                        prompt_tokens = _safe_int(raw_prompt, 0)
                        completion_tokens = _safe_int(raw_completion, 0)

                        if raw_total is not None:
                            total_tokens = _safe_int(raw_total, prompt_tokens + completion_tokens)
                        else:
                            total_tokens = prompt_tokens + completion_tokens

                        prompt_tokens_details = _get_usage_attr(usage, "prompt_tokens_details")
                        raw_cached = _get_usage_attr(prompt_tokens_details, "cached_tokens")
                        cached_prompt_tokens = _safe_int(raw_cached, 0)

                        uncached_prompt_tokens = max(0, prompt_tokens - cached_prompt_tokens)
                        is_estimated = False
                    else:
                        prompt_tokens = len(str(messages)) // 4
                        cached_prompt_tokens = 0
                        uncached_prompt_tokens = prompt_tokens
                        completion_tokens = len(content) // 4
                        total_tokens = prompt_tokens + completion_tokens
                        is_estimated = True

                    cost, pricing_key, p_ver = calculate_token_cost(
                        self.model_id,
                        uncached_prompt_tokens=uncached_prompt_tokens,
                        completion_tokens=completion_tokens,
                        cached_prompt_tokens=cached_prompt_tokens,
                        fail_fast=True
                    )

                    return LLMResponseDTO(
                        content=content,
                        tool_calls=extracted_tool_calls,
                        prompt_tokens=prompt_tokens,
                        cached_prompt_tokens=cached_prompt_tokens,
                        uncached_prompt_tokens=uncached_prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        is_estimated_tokens=is_estimated,
                        estimated_cost_usd=cost,
                        latency_ms=round(latency_ms, 2),
                        provider=self.provider,
                        model_id=self.model_id,
                        model_snapshot=self.model_snapshot,
                        endpoint=self.endpoint,
                        temperature=temp,
                        seed_requested=target_seed,
                        seed_supported=self.seed_supported,
                        seed_applied=actual_seed_applied,
                        pricing_version=p_ver,
                        pricing_model_key=pricing_key,
                        llm_call_count=attempt_count,
                        successful_llm_call_count=success_count,
                        retry_count=retry_count
                    )
                except Exception as e:
                    last_exception = e
                    err_msg = str(e).lower()
                    
                    # Classification 1: Non-Retryable Provider Quota Error (HTTP 429 / resource_exhausted / quota)
                    if "quota" in err_msg or "insufficient_quota" in err_msg or "resource_exhausted" in err_msg or "429" in err_msg:
                        logger.error(f"Non-retryable provider quota error on attempt {attempt_count}: {e}")
                        raise ProviderQuotaError(f"PROVIDER_QUOTA_ERROR: Provider quota exceeded for model '{self.model_id}'. Details: {e}")

                    logger.warning(f"Live API call attempt {attempt_count} failed: {e}")

            # If all retries fail, raise RuntimeError immediately (NEVER fall back to mock when API key is configured!)
            raise RuntimeError(
                f"PROVIDER_ERROR: All {attempt_count} live API retries failed for model '{self.model_id}'. Last error: {last_exception}"
            )

        # 3. Offline Mock Fallback (ONLY allowed when NO valid API key is present AND require_live_api is False)
        if self.require_live_api:
            raise ValueError("FAIL-FAST: LIVE_API required but API key missing or invalid.")

        return self._simulate_response(messages, tools, start_time, temp, target_seed)

    def _simulate_response(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]],
        start_time: float,
        temp: float,
        seed: Optional[int]
    ) -> LLMResponseDTO:
        user_query = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_query = m.get("content", "")
                break

        content = "This is a simulated response based on the input query."
        tool_calls = []
        query_lower = user_query.lower()

        if tools:
            if "create purchase order" in query_lower or "order" in query_lower:
                if "sku-1001" in query_lower or "sup-101" in query_lower:
                    qty = 20 if "20" in query_lower else 10
                    tool_calls.append({
                        "id": "call_sim_02",
                        "function": {
                            "name": "create_purchase_order",
                            "arguments": f'{{"sku": "SKU-1001", "qty": {qty}, "supplier_id": "SUP-101", "unit_price": 870.0}}'
                        }
                    })
                elif "sku-1005" in query_lower or "sup-105" in query_lower:
                    tool_calls.append({
                        "id": "call_sim_03",
                        "function": {
                            "name": "create_purchase_order",
                            "arguments": "{\"sku\": \"SKU-1005\", \"qty\": 2, \"supplier_id\": \"SUP-105\", \"unit_price\": 950.0}"
                        }
                    })
                else:
                    tool_calls.append({
                        "id": "call_sim_02",
                        "function": {
                            "name": "create_purchase_order",
                            "arguments": "{\"sku\": \"SKU-1002\", \"qty\": 2, \"supplier_id\": \"SUP-102\", \"unit_price\": 155.0}"
                        }
                    })
            elif "check inventory" in query_lower or "stock" in query_lower or "sku-" in query_lower:
                tool_calls.append({
                    "id": "call_sim_01",
                    "function": {
                        "name": "check_inventory",
                        "arguments": "{\"sku\": \"SKU-1001\"}"
                    }
                })

        if "spending limit" in query_lower or "threshold" in query_lower:
            content = "According to Section 1 of the Procurement Policy, Level 1 Procurement Agents have an authorized financial threshold up to $5,000.00 USD per purchase order before escalation is required."
        elif "return policy" in query_lower or "apex" in query_lower:
            content = "For Apex Office Logistics (SUP-102), the return policy window is 14 Days with a full refund and a 10% restocking fee on assembled furniture."

        prompt_tokens = len(str(messages)) // 4
        completion_tokens = len(content) // 4 + 20
        total_tokens = prompt_tokens + completion_tokens
        latency_ms = (time.perf_counter() - start_time) * 1000.0 + 15.0
        cost, pricing_key, p_ver = calculate_token_cost(self.model_id, prompt_tokens, completion_tokens, fail_fast=False)

        return LLMResponseDTO(
            content=content,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            cached_prompt_tokens=0,
            uncached_prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            is_estimated_tokens=True,
            estimated_cost_usd=cost,
            latency_ms=round(latency_ms, 2),
            provider=self.provider,
            model_id=self.model_id,
            model_snapshot=self.model_snapshot,
            endpoint=self.endpoint,
            temperature=temp,
            seed_requested=seed,
            seed_supported=False,
            seed_applied=None,
            pricing_version=p_ver,
            pricing_model_key=pricing_key,
            llm_call_count=1,
            successful_llm_call_count=1,
            retry_count=0
        )
