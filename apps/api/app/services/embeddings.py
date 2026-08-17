import hashlib
import math
import re
import httpx
from app.config import get_settings

DIM = 384
TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{1,}")


def demo_embedding(text: str) -> list[float]:
    vec = [0.0] * DIM
    tokens = TOKEN_RE.findall(text.lower())
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest, "big") % DIM
        sign = 1.0 if digest[0] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def fold_embedding(values: list[float]) -> list[float]:
    if len(values) == DIM:
        return values
    out = [0.0] * DIM
    for i, value in enumerate(values):
        out[i % DIM] += float(value)
    norm = math.sqrt(sum(v * v for v in out)) or 1.0
    return [v / norm for v in out]


def embed_text(text: str) -> list[float]:
    settings = get_settings()
    if settings.embedding_mode != "openai_compatible":
        return demo_embedding(text)

    base_url = settings.embedding_base_url or settings.ai_base_url
    api_key = settings.embedding_api_key or settings.ai_api_key
    model = settings.embedding_model
    if not model:
        raise RuntimeError("EMBEDDING_MODEL is required for openai_compatible embeddings")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    with httpx.Client(timeout=settings.ai_timeout_seconds) as client:
        response = client.post(
            f"{base_url.rstrip('/')}/embeddings",
            headers=headers,
            json={"model": model, "input": text},
        )
        response.raise_for_status()
        values = response.json()["data"][0]["embedding"]
    return fold_embedding(values)
