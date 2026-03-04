import asyncio
import logging
from dataclasses import dataclass

import voyageai

logger = logging.getLogger("vault-agent")

MODEL = "voyage-3-lite"
BATCH_SIZE = 128
MAX_RETRIES = 3
BATCH_SLEEP_S = 1.0  # stay within free-tier rate limits


@dataclass
class EmbeddingResult:
    embeddings: list[list[float]]
    total_tokens: int


async def embed_texts(
    api_key: str, texts: list[str], input_type: str = "document"
) -> EmbeddingResult:
    client = voyageai.AsyncClient(api_key=api_key)

    all_embeddings: list[list[float]] = []
    total_tokens = 0

    for i in range(0, len(texts), BATCH_SIZE):
        if i > 0:
            await asyncio.sleep(BATCH_SLEEP_S)

        batch = texts[i : i + BATCH_SIZE]

        for attempt in range(MAX_RETRIES):
            try:
                result = await client.embed(batch, model=MODEL, input_type=input_type)
                all_embeddings.extend(result.embeddings)
                total_tokens += result.total_tokens
                break
            except Exception as e:
                err_str = str(e).lower()
                if "payment method" in err_str:
                    raise RuntimeError(
                        "Voyage AI requires a payment method to lift rate limits. "
                        "Add one at https://dashboard.voyageai.com/ — the first 200M tokens remain free."
                    ) from e
                is_rate_limit = any(
                    kw in err_str for kw in ("429", "rate limit", "too many requests")
                )
                if attempt < MAX_RETRIES - 1 and is_rate_limit:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Rate limited by Voyage AI, retrying in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    raise

    return EmbeddingResult(embeddings=all_embeddings, total_tokens=total_tokens)


async def embed_query(api_key: str, query: str) -> list[float]:
    client = voyageai.AsyncClient(api_key=api_key)
    result = await client.embed([query], model=MODEL, input_type="query")
    return result.embeddings[0]
