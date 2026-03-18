import asyncio
import logging

import anthropic

from src.models import TokenUsage

logger = logging.getLogger("vault-agent")

MODELS = {
    "haiku": {
        "id": "claude-haiku-4-5",
        "label": "Haiku 4.5",
        "input": 1.00,
        "output": 5.00,
        "cache_write": 1.25,
        "cache_read": 0.10,
    },
    "sonnet": {
        "id": "claude-sonnet-4-6",
        "label": "Sonnet 4.6",
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
}
DEFAULT_MODEL = "sonnet"
_BATCH_DISCOUNT = 0.5


# Compute LLM API cost in USD from token counts and model pricing.
#
# When include_cache_savings is True, cache write/read tokens use their
# discounted rates. Otherwise all input tokens use the base input rate.
# Batch API calls get a 50% discount.
#
# Args:
#     input_tokens: Non-cached input token count.
#     output_tokens: Output token count.
#     cache_write_tokens: Tokens written to prompt cache.
#     cache_read_tokens: Tokens read from prompt cache.
#     model_key: Key into MODELS pricing dict.
#     is_batch: Apply batch API discount.
#     include_cache_savings: Use cache-specific pricing rates.
#
# Returns:
#     Estimated cost in USD.
def compute_cost(
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int,
    cache_read_tokens: int,
    model_key: str = DEFAULT_MODEL,
    is_batch: bool = False,
    include_cache_savings: bool = False,
) -> float:
    pricing = MODELS[model_key]
    if include_cache_savings:
        cost = (
            input_tokens * pricing["input"] / 1_000_000
            + output_tokens * pricing["output"] / 1_000_000
            + cache_write_tokens * pricing["cache_write"] / 1_000_000
            + cache_read_tokens * pricing["cache_read"] / 1_000_000
        )
    else:
        total_input = input_tokens + cache_write_tokens + cache_read_tokens
        cost = (
            total_input * pricing["input"] / 1_000_000
            + output_tokens * pricing["output"] / 1_000_000
        )
    return cost * _BATCH_DISCOUNT if is_batch else cost


# Construct a TokenUsage object from raw token counts.
#
# Args:
#     input_tokens: Non-cached input token count.
#     output_tokens: Output token count.
#     cache_write_tokens: Tokens written to prompt cache.
#     cache_read_tokens: Tokens read from prompt cache.
#     api_calls: Number of API calls made.
#     tool_calls: Number of tool calls made.
#     model_key: Key into MODELS pricing dict.
#     is_batch: Whether this was a batch API call.
#
# Returns:
#     TokenUsage with computed cost.
def build_token_usage(
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int,
    cache_read_tokens: int,
    api_calls: int,
    tool_calls: int,
    model_key: str = DEFAULT_MODEL,
    is_batch: bool = False,
) -> TokenUsage:
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_write_tokens=cache_write_tokens,
        cache_read_tokens=cache_read_tokens,
        api_calls=api_calls,
        tool_calls=tool_calls,
        is_batch=is_batch,
        model=model_key,
        total_cost_usd=compute_cost(
            input_tokens,
            output_tokens,
            cache_write_tokens,
            cache_read_tokens,
            model_key,
            is_batch,
        ),
    )


# Extract token counts from an Anthropic API response.
#
# Args:
#     response: Raw Anthropic API response object.
#
# Returns:
#     Tuple of (input, output, cache_write, cache_read) token counts.
def extract_usage(response) -> tuple[int, int, int, int]:
    u = response.usage
    return (
        u.input_tokens,
        u.output_tokens,
        getattr(u, "cache_creation_input_tokens", 0) or 0,
        getattr(u, "cache_read_input_tokens", 0) or 0,
    )


# Call client.messages.create with exponential backoff on rate limits.
#
# Retries up to 3 times on 429 (rate limit) and 529 (overloaded) errors
# with exponential delay.
#
# Args:
#     client: Anthropic async client.
#     **kwargs: Arguments passed to client.messages.create.
#
# Returns:
#     Anthropic API response.
#
# Raises:
#     anthropic.RateLimitError: After all retries exhausted on 429.
#     anthropic.APIStatusError: On non-retryable API errors.
async def create_with_retry(client: anthropic.AsyncAnthropic, **kwargs):
    max_retries = 3
    base_delay = 1.0

    for attempt in range(max_retries + 1):
        try:
            return await client.messages.create(**kwargs)
        except anthropic.RateLimitError:
            if attempt == max_retries:
                raise
            delay = base_delay * (2**attempt)
            logger.warning(
                "Rate limited (429), retrying in %.1fs (attempt %d/%d)",
                delay,
                attempt + 1,
                max_retries,
            )
            await asyncio.sleep(delay)
        except anthropic.APIStatusError as err:
            if err.status_code == 529 and attempt < max_retries:
                delay = base_delay * (2**attempt)
                logger.warning(
                    "API overloaded (529), retrying in %.1fs (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(delay)
            else:
                raise
