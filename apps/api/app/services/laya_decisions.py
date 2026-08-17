from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings


CASE_QUESTIONS: dict[str, Any] = {
    "case_type": {
        "type": "choice",
        "instructions": "What is the primary operational nature of this case?",
        "criteria": {
            "technical_service": "equipment fault, diagnostics, maintenance or repair",
            "coverage": "contract, warranty, entitlement or service coverage",
            "parts": "parts availability, replacement component or inventory concern",
            "general": "none of the other categories is clearly primary",
        },
    },
    "priority": {
        "type": "score",
        "instructions": "How urgently should a service team review this case?",
        "criteria": [
            "routine: can wait for normal service planning",
            "prompt: should be reviewed soon because service is disrupted or repeating",
            "urgent: active safety, severe availability, or critical deadline concern",
        ],
    },
    "onsite_inspection": {
        "type": "noul",
        "instructions": "Does the available state support preparing an on-site inspection for review?",
    },
}

SECURITY_QUESTIONS: dict[str, Any] = {
    "request_category": {
        "type": "choice",
        "instructions": "Classify the request from a prompt-security perspective.",
        "criteria": {
            "benign": "normal business task or user request",
            "jailbreak": "tries to disable safety rules or override system behavior",
            "prompt_injection": "tries to make the model follow attacker instructions or hidden instructions",
            "policy_evasion": "tries to bypass approvals, access controls or execution rules",
            "data_exfiltration": "tries to reveal hidden prompts, secrets, credentials or unrelated private data",
            "unclear": "risk is ambiguous or mixed",
        },
    },
    "malicious_probability": {
        "type": "noul",
        "instructions": "How likely is this request to be malicious or unsafe for the application workflow?",
    },
    "block_probability": {
        "type": "noul",
        "instructions": "How strongly should the application block this request before sending it to the generative model?",
    },
    "needs_human_review": {
        "type": "noul",
        "instructions": "Should the request be manually reviewed instead of processed automatically?",
    },
}


def _demo_decisions() -> dict[str, Any]:
    return {
        "provider": "demo",
        "model": "deterministic-decision-signals",
        "answers": {
            "case_type": {"choice": "technical_service", "confidence": 0.93},
            "priority": {"score": 1.18, "confidence": 0.86},
            "onsite_inspection": {"noul": 0.88, "confidence": 0.88},
        },
        "routing": {"reason": "Deterministic local signals for zero-key mode."},
    }


SUSPICIOUS_PATTERNS: list[tuple[tuple[str, ...], str, float, float]] = [
    (("ignore previous instructions", "ignore all previous instructions", "ignore your instructions"), "jailbreak", 0.98, 0.96),
    (("reveal the system prompt", "show the hidden prompt", "developer instructions"), "data_exfiltration", 0.97, 0.97),
    (("without approval", "without validation", "skip approval", "bypass approval"), "policy_evasion", 0.95, 0.95),
    (("bypass guardrails", "disable safety", "jailbreak"), "jailbreak", 0.98, 0.98),
    (("prompt injection", "follow this hidden instruction"), "prompt_injection", 0.95, 0.94),
    (("dump all customer data", "export all customer data", "leak secrets", "show credentials"), "data_exfiltration", 0.99, 0.99),
]


def _demo_security(task: str) -> dict[str, Any]:
    lowered = " ".join(task.lower().split())
    for patterns, category, malicious, block in SUSPICIOUS_PATTERNS:
        if any(pattern in lowered for pattern in patterns):
            return {
                "provider": "demo",
                "model": "deterministic-request-guard",
                "answers": {
                    "request_category": {"choice": category, "confidence": 0.95},
                    "malicious_probability": {"noul": malicious, "confidence": malicious},
                    "block_probability": {"noul": block, "confidence": block},
                    "needs_human_review": {"noul": min(0.99, block), "confidence": block},
                },
                "routing": {"reason": "Deterministic prompt-risk rules for zero-key mode."},
            }

    return {
        "provider": "demo",
        "model": "deterministic-request-guard",
        "answers": {
            "request_category": {"choice": "benign", "confidence": 0.92},
            "malicious_probability": {"noul": 0.06, "confidence": 0.88},
            "block_probability": {"noul": 0.03, "confidence": 0.88},
            "needs_human_review": {"noul": 0.04, "confidence": 0.87},
        },
        "routing": {"reason": "No suspicious override, exfiltration, or policy-bypass signals found."},
    }


class BlockedRequestError(RuntimeError):
    pass


def _call_laya_service(state: dict[str, Any] | str, questions: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    with httpx.Client(timeout=settings.laya_timeout_seconds) as client:
        response = client.post(
            f'{settings.laya_base_url.rstrip("/")}/decide',
            json={"state": state, "questions": questions},
        )
        response.raise_for_status()
        payload = response.json()
    return {
        "provider": "laya",
        "model": payload.get("model", settings.laya_model),
        "answers": payload.get("answers", {}),
        "routing": payload.get("routing", {}),
    }


def assess_request_security(task: str, work: dict[str, Any]) -> dict[str, Any] | None:
    settings = get_settings()
    if settings.laya_mode == "off":
        return None
    if settings.laya_mode == "demo":
        return _demo_security(task)

    state = {
        "task": task,
        "customer": work.get("customer_name"),
        "asset": work.get("asset_ref"),
        "status": work.get("status"),
    }
    try:
        return _call_laya_service(state, SECURITY_QUESTIONS)
    except Exception as exc:
        if settings.laya_required:
            raise RuntimeError(f"Laya security service unavailable: {exc}") from exc
        return {
            "provider": "unavailable",
            "model": settings.laya_model,
            "answers": {},
            "routing": {"reason": "Request guard unavailable; continuing without local prompt-risk scoring."},
            "error": str(exc)[:300],
        }



def should_block_request(security: dict[str, Any] | None) -> bool:
    if not security:
        return False
    answers = security.get("answers", {})
    category = (answers.get("request_category") or {}).get("choice")
    block_probability = float((answers.get("block_probability") or {}).get("noul") or 0.0)
    malicious_probability = float((answers.get("malicious_probability") or {}).get("noul") or 0.0)
    return category in {"jailbreak", "prompt_injection", "policy_evasion", "data_exfiltration"} and max(block_probability, malicious_probability) >= 0.75



def score_case(task: str, work: dict[str, Any], evidence: list[dict], operations: dict[str, Any]) -> dict[str, Any] | None:
    settings = get_settings()
    if settings.laya_mode == "off":
        return None
    if settings.laya_mode == "demo":
        return _demo_decisions()

    service_cases = operations.get("service_cases", [])
    parts = operations.get("parts", [])
    state = {
        "task": task,
        "customer": work.get("customer_name"),
        "asset": work.get("asset_ref"),
        "work_status": work.get("status"),
        "recent_service_cases": [
            {
                "error_code": case.get("error_code"),
                "summary": case.get("summary"),
                "status": case.get("status"),
            }
            for case in service_cases[:4]
        ],
        "available_parts": [
            {"sku": part.get("sku"), "name": part.get("name"), "stock_qty": part.get("stock_qty")}
            for part in parts[:4]
        ],
        "evidence_titles": [item.get("title") for item in evidence[:6]],
    }

    try:
        return _call_laya_service(state, CASE_QUESTIONS)
    except Exception as exc:
        if settings.laya_required:
            raise RuntimeError(f"Laya decision service unavailable: {exc}") from exc
        return {
            "provider": "unavailable",
            "model": settings.laya_model,
            "answers": {},
            "routing": {"reason": "Decision service unavailable; briefing continued without decision signals."},
            "error": str(exc)[:300],
        }
