"""Native Mac embedding service: OpenAI-compatible POST /embeddings.

Model: BAAI/bge-small-en-v1.5 (384 dims — matches the API's DIM exactly, so no
folding distortion; ~130 MB; strong English retrieval; fast on MPS/CPU).

Run natively (see apps/laya/README.md for the same pattern):

    EMB_MODEL=BAAI/bge-small-en-v1.5 EMB_DEVICE=mps nohup \
      /path/to/.venv-laya/bin/python -m uvicorn app:app \
      --host 0.0.0.0 --port 8090 --app-dir apps/embeddings \
      > /tmp/embeddings-mac.log 2>&1 &

Then point the API at it:

    EMBEDDING_MODE=openai_compatible
    EMBEDDING_BASE_URL=http://host.docker.internal:8090
    EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

IMPORTANT: existing chunks were embedded with a different space. After
switching modes, re-embed all chunks (see README section "Re-embedding").
"""

import os
import time

from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

MODEL_NAME = os.environ.get("EMB_MODEL", "BAAI/bge-small-en-v1.5")


def auto_device() -> str:
    """Resolve the device: EMB_DEVICE override, else auto-detect
    MPS (Apple Silicon GPU) > CUDA (NVIDIA) > CPU."""
    override = os.environ.get("EMB_DEVICE", "").strip().lower()
    if override in {"mps", "cuda", "cpu"}:
        return override
    try:
        import torch

        if torch.backends.mps.is_available() and torch.backends.mps.is_built():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except Exception:  # pragma: no cover - torch optional
        pass
    return "cpu"


DEVICE = auto_device()

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        try:
            _model = SentenceTransformer(MODEL_NAME, device=DEVICE)
        except Exception:
            _model = SentenceTransformer(MODEL_NAME, device="cpu")
    return _model


class EmbedRequest(BaseModel):
    model: str = ""
    input: str | list[str]


app = FastAPI(title="Service Desk embeddings", version="0.1.0")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "device": DEVICE,
        "loaded": _model is not None,
    }


@app.post("/embeddings")
def embeddings(payload: EmbedRequest):
    started = time.perf_counter()
    texts = payload.input if isinstance(payload.input, list) else [payload.input]
    vectors = get_model().encode(texts, normalize_embeddings=True).tolist()
    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": i, "embedding": vec}
            for i, vec in enumerate(vectors)
        ],
        "model": payload.model or MODEL_NAME,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }
