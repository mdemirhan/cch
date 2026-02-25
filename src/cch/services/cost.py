"""Model pricing table and cost estimation."""

from __future__ import annotations

# Prices per million tokens (USD) — as of Feb 2026
# Source: Anthropic pricing page
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-5-20251101": {
        "input": 15.0,
        "output": 75.0,
        "cache_read": 1.5,
        "cache_creation": 18.75,
    },
    "claude-opus-4-6": {
        "input": 15.0,
        "output": 75.0,
        "cache_read": 1.5,
        "cache_creation": 18.75,
    },
    "claude-sonnet-4-5-20251022": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.3,
        "cache_creation": 3.75,
    },
    "claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.3,
        "cache_creation": 3.75,
    },
    "claude-haiku-4-5-20251001": {
        "input": 0.80,
        "output": 4.0,
        "cache_read": 0.08,
        "cache_creation": 1.0,
    },
}

# Default pricing for unknown models (use Sonnet-level pricing)
DEFAULT_PRICING: dict[str, float] = {
    "input": 3.0,
    "output": 15.0,
    "cache_read": 0.3,
    "cache_creation": 3.75,
}


def get_pricing(model: str) -> dict[str, float]:
    """Get pricing for a model, falling back to default."""
    return MODEL_PRICING.get(model, DEFAULT_PRICING)


def estimate_cost(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
) -> dict[str, float]:
    """Estimate cost for token usage.

    Returns:
        Dict with input_cost, output_cost, cache_read_cost, cache_creation_cost, total_cost.
    """
    pricing = get_pricing(model)
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    cache_read_cost = (cache_read_tokens / 1_000_000) * pricing["cache_read"]
    cache_creation_cost = (cache_creation_tokens / 1_000_000) * pricing["cache_creation"]

    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "cache_read_cost": cache_read_cost,
        "cache_creation_cost": cache_creation_cost,
        "total_cost": input_cost + output_cost + cache_read_cost + cache_creation_cost,
    }
