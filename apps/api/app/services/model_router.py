from __future__ import annotations
import json
import re
import time
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models import ModelEndpoint

SENSITIVITY_ORDER = {"public": 0, "internal": 1, "restricted": 2}


class ModelResult(dict):
    pass


def route_model(db: Session, organization_id: int, sensitivity: str, capability: str = "reasoning") -> dict:
    settings = get_settings()
    if settings.ai_mode == "demo":
        return {
            "provider": "demo",
            "model": "service-desk-demo",
            "base_url": None,
            "route_reason": "Deterministic demo provider selected for zero-key local execution.",
            "kind": "demo",
        }

    candidates = db.scalars(select(ModelEndpoint).where(
        ModelEndpoint.organization_id == organization_id,
        ModelEndpoint.enabled.is_(True),
        ModelEndpoint.healthy.is_(True),
    ).order_by(ModelEndpoint.priority.asc())).all()

    eligible = []
    required = SENSITIVITY_ORDER.get(sensitivity, 1)
    for endpoint in candidates:
        ceiling = SENSITIVITY_ORDER.get(endpoint.max_sensitivity, 1)
        if ceiling < required:
            continue
        if capability not in (endpoint.capabilities or []):
            continue
        eligible.append(endpoint)

    if eligible:
        endpoint = eligible[0]
        return {
            "provider": endpoint.name,
            "model": endpoint.model,
            "base_url": endpoint.base_url or settings.ai_base_url,
            "route_reason": f"Allowed for {sensitivity} data; {capability} capable; highest configured priority among healthy endpoints.",
            "kind": endpoint.kind,
        }

    # A single environment-configured endpoint is the simple v1 path. Its privacy
    # ceiling is explicit so a local endpoint can be approved for restricted data
    # while an ordinary cloud endpoint can remain internal/public only.
    env_ceiling = SENSITIVITY_ORDER.get(settings.ai_max_sensitivity, 1)
    if env_ceiling < required:
        raise RuntimeError(f"No approved model endpoint is available for {sensitivity} data")
    if not settings.ai_model:
        raise RuntimeError("AI_MODEL is required in openai_compatible mode")
    return {
        "provider": "environment",
        "model": settings.ai_model,
        "base_url": settings.ai_base_url,
        "route_reason": f"Environment {settings.ai_provider_kind} endpoint is approved up to {settings.ai_max_sensitivity} and selected for {sensitivity} data.",
        "kind": settings.ai_provider_kind,
    }


def generate_briefing(route: dict, task: str, work: dict, evidence: list[dict], operations: dict, decisions: dict | None = None) -> dict:
    if route["kind"] == "demo":
        return _demo_briefing(task, work, evidence, operations, decisions)

    settings = get_settings()
    allowed_ids = [item["id"] for item in evidence]
    source_text = "\n\n".join(
        f'[{item["id"]}] {item["title"]} / {item.get("section") or "Excerpt"}\n{item["text"]}'
        for item in evidence
    )
    prompt = f"""You are preparing a technical service escalation brief. Use only the supplied evidence and structured records.
Never invent citations. Citation IDs must come from this list: {allowed_ids}.
Return ONLY valid JSON with this shape:
{{
  "title": string,
  "summary": string,
  "sections": [{{"heading": string, "body": string, "citations": [string]}}],
  "next_steps": [string],
  "citations": [string],
  "action_proposal": null OR {{"type":"create_work_order","summary":string,"requested_work":string,"evidence_ids":[string]}}
}}
If evidence is insufficient, say so and do not propose an action.

Task: {task}
Work item: {json.dumps(work, default=str)}
Operational decision signals: {json.dumps((decisions or {}).get("answers", {}), default=str)}
These signals are advisory triage output only and must not be treated as authorization.
Structured operations data: {json.dumps(operations, default=str)}
Evidence:\n{source_text}
"""
    headers = {"Content-Type": "application/json"}
    if settings.ai_api_key:
        headers["Authorization"] = f"Bearer {settings.ai_api_key}"
    started = time.perf_counter()
    with httpx.Client(timeout=settings.ai_timeout_seconds) as client:
        response = client.post(
            f'{route["base_url"].rstrip("/")}/chat/completions',
            headers=headers,
            json={
                "model": route["model"],
                "messages": [
                    {"role": "system", "content": "You produce concise, evidence-backed service briefs as JSON."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
            },
        )
        response.raise_for_status()
        payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    parsed = _parse_json(content)
    decision_answers = (decisions or {}).get("answers", {})
    parsed["decision_signals"] = {
        "provider": (decisions or {}).get("provider"),
        "model": (decisions or {}).get("model"),
        "case_type": (decision_answers.get("case_type") or {}).get("choice"),
        "case_type_confidence": (decision_answers.get("case_type") or {}).get("confidence"),
        "priority_score": (decision_answers.get("priority") or {}).get("score"),
        "onsite_probability": (decision_answers.get("onsite_inspection") or {}).get("noul"),
    }
    usage = payload.get("usage") or {}
    return {
        "artifact": parsed,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
    }


def _parse_json(content: str) -> dict:
    content = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.S)
    if fenced:
        content = fenced.group(1)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "title": "Service brief",
            "summary": content,
            "sections": [],
            "next_steps": ["Review the generated response and supporting sources."],
            "citations": [],
            "action_proposal": None,
        }


def _demo_briefing(task: str, work: dict, evidence: list[dict], operations: dict, decisions: dict | None = None) -> dict:
    ids = [e["id"] for e in evidence]
    bulletins = [e for e in evidence if "E-217" in e["text"] or "E-217" in e["title"]]
    contract = [e for e in evidence if "agreement" in e["title"].lower() or "warranty" in e["title"].lower()]
    technical_ids = [e["id"] for e in bulletins[:2]] or ids[:2]
    contract_ids = [e["id"] for e in contract[:1]]
    cases = operations.get("service_cases", [])
    repeated = len([c for c in cases if c.get("error_code") == "E-217"])
    parts = operations.get("parts", [])
    stock_line = ", ".join(f'{p["sku"]} ({p["stock_qty"]} in stock)' for p in parts[:3]) or "No compatible parts returned"

    decision_answers = (decisions or {}).get("answers", {})
    artifact = {
        "title": f'{work["customer_name"]} — {work["asset_ref"]} escalation brief',
        "summary": f"The asset has repeated E-217 service history after the firmware 4.8 change. The available service guidance supports an on-site inspection before broader component replacement; coverage and parts should be confirmed before dispatch.",
        "decision_signals": {
            "provider": (decisions or {}).get("provider"),
            "model": (decisions or {}).get("model"),
            "case_type": (decision_answers.get("case_type") or {}).get("choice"),
            "case_type_confidence": (decision_answers.get("case_type") or {}).get("confidence"),
            "priority_score": (decision_answers.get("priority") or {}).get("score"),
            "onsite_probability": (decision_answers.get("onsite_inspection") or {}).get("noul"),
        },
        "sections": [
            {
                "heading": "Situation",
                "body": f'{work["customer_name"]} reports repeated stops on {work["asset_ref"]}. The service database contains {repeated} recent E-217 case(s) for this asset.',
                "citations": technical_ids[:1],
            },
            {
                "heading": "Technical evidence",
                "body": "The PX-400 troubleshooting guidance links E-217 to intermittent encoder or harness faults and asks technicians to inspect the connector path and run the encoder diagnostic before replacement.",
                "citations": technical_ids,
            },
            {
                "heading": "Coverage",
                "body": "The maintenance agreement includes corrective on-site service for covered equipment, subject to the agreement conditions in the customer record.",
                "citations": contract_ids,
            },
            {
                "heading": "Parts availability",
                "body": f"Compatible service inventory currently shows: {stock_line}.",
                "citations": [],
            },
        ],
        "next_steps": [
            "Confirm the latest fault timestamp and whether the stop can be reproduced safely.",
            "Inspect the encoder connector/harness and run the documented E-217 diagnostic.",
            "Use the service work order to reserve the appropriate replacement part only if inspection supports it.",
        ],
        "citations": list(dict.fromkeys(technical_ids + contract_ids)),
        "action_proposal": {
            "type": "create_work_order",
            "summary": f'Inspect repeated E-217 faults on {work["asset_ref"]}',
            "requested_work": "On-site PX-400 inspection: verify encoder connector/harness, run E-217 diagnostic, capture fault logs, and replace the encoder assembly only if diagnostic evidence supports replacement.",
            "evidence_ids": list(dict.fromkeys(technical_ids + contract_ids)),
        },
    }
    return {"artifact": artifact, "latency_ms": 42, "input_tokens": None, "output_tokens": None}
