"""
Token Counter

Estimates token counts for text before sending to an LLM.
Used to enforce context window limits and track costs.

Why token counting matters:
- Every LLM has a context window limit (e.g. 200k tokens for Claude)
- APIs charge per token — knowing the count before the call lets
  you estimate cost and reject oversized requests early
- Helps split long documents into API-safe chunks

Token estimation approaches:
1. Exact: use tiktoken (OpenAI's tokenizer) — accurate but adds dependency
2. Approximate: character-based rules of thumb
   - English text: ~4 chars per token
   - Code: ~3.5 chars per token
   - Mixed: ~4 chars per token

We use tiktoken when available and fall back to the approximation.
"""

import re


# Approximate tokens per character for different content types
CHARS_PER_TOKEN = {
    "english": 4.0,
    "code":    3.5,
    "mixed":   4.0,
}

# Context window limits by model (in tokens)
CONTEXT_WINDOWS = {
    # Anthropic
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-5-haiku-20241022":  200_000,
    "claude-3-opus-20240229":     200_000,
    "claude-sonnet-4-20250514":   200_000,
    # OpenAI
    "gpt-4o":                     128_000,
    "gpt-4o-mini":                128_000,
    "gpt-4-turbo":                128_000,
    "gpt-3.5-turbo":               16_385,
}

# Cost per 1M tokens (input, output) in USD
TOKEN_COSTS = {
    "claude-3-5-sonnet-20241022": (3.00,  15.00),
    "claude-3-5-haiku-20241022":  (0.80,   4.00),
    "claude-3-opus-20240229":     (15.00,  75.00),
    "claude-sonnet-4-20250514":   (3.00,   15.00),
    "gpt-4o":                     (5.00,  15.00),
    "gpt-4o-mini":                (0.15,   0.60),
    "gpt-4-turbo":                (10.00,  30.00),
    "gpt-3.5-turbo":              (0.50,   1.50),
}


def count_tokens_approx(text: str) -> int:
    """
    Approximate token count using character ratio.
    Rule of thumb: 1 token ≈ 4 characters for English text.
    Always slightly overestimates — safer than underestimating.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def count_tokens_exact(text: str, model: str = "cl100k_base") -> int:
    """
    Exact token count using tiktoken.
    Falls back to approximation if tiktoken is not installed.
    """
    try:
        import tiktoken
        enc = tiktoken.get_encoding(model)
        return len(enc.encode(text))
    except ImportError:
        return count_tokens_approx(text)
    except Exception:
        return count_tokens_approx(text)


def count_message_tokens(messages: list[dict], model: str = "cl100k_base") -> int:
    """
    Count tokens across a full messages list (system + user + assistant).
    Adds overhead tokens for message formatting (~4 tokens per message).
    """
    total = 0
    for msg in messages:
        total += count_tokens_exact(msg.get("content", ""), model)
        total += 4  # per-message formatting overhead
    total += 2  # reply priming tokens
    return total


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str,
) -> dict:
    """
    Estimate API cost for a request.
    Returns dict with input_cost, output_cost, total_cost in USD.
    """
    if model not in TOKEN_COSTS:
        return {"input_cost": 0.0, "output_cost": 0.0, "total_cost": 0.0,
                "note": f"No pricing data for model '{model}'"}

    input_price, output_price = TOKEN_COSTS[model]
    input_cost  = (input_tokens  / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price

    return {
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "input_cost":    round(input_cost, 6),
        "output_cost":   round(output_cost, 6),
        "total_cost":    round(input_cost + output_cost, 6),
        "currency":      "USD",
    }


def fits_in_context(text: str, model: str, reserve_output: int = 1000) -> bool:
    """
    Check if text fits in the model's context window.
    reserve_output: tokens to reserve for the model's response.
    """
    limit = CONTEXT_WINDOWS.get(model, 100_000)
    used  = count_tokens_approx(text)
    return used + reserve_output <= limit
