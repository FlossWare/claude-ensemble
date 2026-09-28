"""
Pricing constants for Claude models and integration partners.
Updated: 2026-09-25
Source: official Claude pricing and integration partners
"""

# Claude Model Pricing (USD per 1M tokens)
CLAUDE_PRICING = {
    "haiku": {
        "input": 0.80,
        "output": 2.40,
        "name": "Claude Haiku 4.5"
    },
    "sonnet": {
        "input": 3.00,
        "output": 15.00,
        "name": "Claude Sonnet 4.5"
    },
    "opus": {
        "input": 15.00,
        "output": 45.00,
        "name": "Claude Opus 5"
    },
    "opus-4.8": {
        "input": 12.00,
        "output": 36.00,
        "name": "Claude Opus 4.8"
    }
}

# Integration Partner Pricing (for reference)
GEMINI_PRICING = {
    "input": 0.075,
    "output": 0.30,
    "name": "Google Gemini"
}

GPT_PRICING = {
    "gpt-4o": {
        "input": 5.00,
        "output": 15.00,
        "name": "GPT-4o"
    },
    "gpt-4-turbo": {
        "input": 10.00,
        "output": 30.00,
        "name": "GPT-4 Turbo"
    }
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost for an API call.

    Args:
        model: Model name (e.g., "haiku", "sonnet", "opus")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD (float)
    """
    model_lower = model.lower()

    if model_lower not in CLAUDE_PRICING:
        raise ValueError(f"Unknown model: {model}. Known models: {list(CLAUDE_PRICING.keys())}")

    pricing = CLAUDE_PRICING[model_lower]

    # Cost = (input_tokens / 1M) * input_price + (output_tokens / 1M) * output_price
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return input_cost + output_cost


def get_model_display_name(model: str) -> str:
    """Get display name for a model."""
    model_lower = model.lower()
    if model_lower in CLAUDE_PRICING:
        return CLAUDE_PRICING[model_lower]["name"]
    return model
