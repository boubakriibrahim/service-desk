from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

os.environ.setdefault("USE_TF", "0")

app = FastAPI(title="Service Desk Local Laya Service", version="1.1.0")


class DecisionRequest(BaseModel):
    state: dict[str, Any] | str
    questions: dict[str, Any]
    model: str | None = None


class DecisionResponse(BaseModel):
    model: str
    answers: dict[str, Any]
    routing: dict[str, Any] = Field(default_factory=dict)


@lru_cache(maxsize=1)
def _auto_device() -> str:
    """Resolve the inference device: LAYA_DEVICE override, else auto-detect
    MPS (Apple Silicon GPU) > CUDA (NVIDIA) > CPU."""
    override = os.getenv("LAYA_DEVICE", "").strip().lower()
    if override in {"mps", "cuda", "cpu"}:
        return override
    try:
        import torch

        if torch.backends.mps.is_available() and torch.backends.mps.is_built():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except Exception:  # pragma: no cover - torch optional at import time
        pass
    return "cpu"


@lru_cache(maxsize=1)
def _router():
    try:
        from laya import Router
    except ImportError as exc:  # pragma: no cover - runtime path
        raise RuntimeError("The optional laya package is not installed") from exc

    preload = os.getenv("LAYA_PRELOAD", "true").strip().lower() not in {
        "0",
        "false",
        "no",
    }
    max_loaded = int(os.getenv("LAYA_MAX_LOADED", "2"))
    return Router(preload=preload, max_loaded=max_loaded, device=_auto_device())


@lru_cache(maxsize=1)
def _single_agent():
    try:
        import laya
    except ImportError as exc:  # pragma: no cover - runtime path
        raise RuntimeError("The optional laya package is not installed") from exc

    model_id = os.getenv("LAYA_MODEL", "convaiinnovations/laya")
    subfolder = os.getenv("LAYA_SUBFOLDER", "").strip() or None
    kwargs: dict[str, Any] = {"device": _auto_device()}
    if subfolder:
        return laya.load(model_id, subfolder=subfolder, **kwargs)
    return laya.load(model_id, **kwargs)


@lru_cache(maxsize=1)
def _strategy() -> str:
    return os.getenv("LAYA_ROUTE_MODE", "router").strip().lower() or "router"


@app.get("/health")
def health():
    return {
        "status": "ok",
        "strategy": _strategy(),
        "model": os.getenv("LAYA_MODEL", "convaiinnovations/laya"),
        "device": _auto_device(),
        "preload": os.getenv("LAYA_PRELOAD", "true"),
        "loaded": (
            _router.cache_info().currsize > 0
            if _strategy() == "router"
            else _single_agent.cache_info().currsize > 0
        ),
    }


@app.post("/decide", response_model=DecisionResponse)
def decide(payload: DecisionRequest):
    try:
        strategy = _strategy()
        if strategy == "single":
            result = _single_agent().predict(payload.state, payload.questions)
            model_name = os.getenv("LAYA_MODEL", "convaiinnovations/laya")
        else:
            router = _router()
            result = router.predict(
                payload.state, payload.questions, model=payload.model
            )
            routing = result.get("routing", {})
            model_name = (
                routing.get("repo")
                or routing.get("model")
                or os.getenv("LAYA_MODEL", "convaiinnovations/laya")
            )
            return DecisionResponse(
                model=model_name, answers=result.get("answers", {}), routing=routing
            )
    except Exception as exc:  # pragma: no cover - model/runtime specific
        raise HTTPException(
            status_code=503, detail=f"Laya decision failed: {exc}"
        ) from exc

    return DecisionResponse(
        model=model_name,
        answers=result.get("answers", {}),
        routing=result.get("routing", {}),
    )
