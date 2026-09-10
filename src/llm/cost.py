from typing import Tuple
from src.config import MODEL_PRICING, PRICING_VERSION

def calculate_token_cost(
    model_name: str,
    uncached_prompt_tokens: int,
    completion_tokens: int,
    cached_prompt_tokens: int = 0,
    fail_fast: bool = False
) -> Tuple[float, str, str]:
    """Calculates dollar cost and returns (cost_usd, pricing_model_key, pricing_version). Fails fast on unknown models."""
    norm_name = model_name.lower()
    
    if norm_name in MODEL_PRICING:
        pricing_key = norm_name
        pricing = MODEL_PRICING[norm_name]
    elif "/" in norm_name and norm_name.split("/", 1)[1] in MODEL_PRICING:
        pricing_key = norm_name.split("/", 1)[1]
        pricing = MODEL_PRICING[pricing_key]
    else:
        if fail_fast:
            raise ValueError(f"Pricing configuration missing for model '{model_name}'. Live cost calculation failed fast.")
        pricing_key = "gpt-4o-mini"
        pricing = MODEL_PRICING["gpt-4o-mini"]
    
    uncached_cost = (uncached_prompt_tokens / 1_000_000.0) * pricing.get("uncached_input_cost_per_1m", 0.15)
    cached_cost = (cached_prompt_tokens / 1_000_000.0) * pricing.get("cached_input_cost_per_1m", 0.075)
    completion_cost = (completion_tokens / 1_000_000.0) * pricing.get("output_cost_per_1m", 0.60)
    
    total_cost = round(uncached_cost + cached_cost + completion_cost, 6)
    return total_cost, pricing_key, PRICING_VERSION
