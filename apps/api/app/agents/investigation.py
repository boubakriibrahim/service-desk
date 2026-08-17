from __future__ import annotations
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.models import Action, Run, RunEvent, WorkItem
from app.services.laya_decisions import assess_request_security, score_case, should_block_request
from app.services.model_router import generate_briefing, route_model
from app.services.operations import get_operations_context
from app.services.retrieval import max_sensitivity, retrieve
from app.services.validation import sanitize_citations


class InvestigationState(TypedDict, total=False):
    security: dict | None
    evidence: list[dict]
    operations: dict
    sensitivity: str
    decisions: dict | None
    route: dict
    result: dict
    action_id: int | None



def _event(db: Session, organization_id: int, run_id: int, kind: str, label: str, detail: dict | None = None):
    db.add(RunEvent(
        organization_id=organization_id,
        run_id=run_id,
        kind=kind,
        label=label,
        detail=detail or {},
    ))
    db.commit()



def _security_snapshot(security: dict | None) -> dict | None:
    if not security:
        return None
    answers = security.get("answers", {})
    category = (answers.get("request_category") or {}).get("choice")
    needs_review = (answers.get("needs_human_review") or {}).get("noul") or 0.0
    # The raw category label is trigger-happy on its own (a benign request can
    # read as "jailbreak" at high confidence). The calibrated block head is the
    # actual decision, so expose it as an explicit verdict for display.
    if should_block_request(security):
        verdict = "blocked"
    elif needs_review >= 0.75:
        verdict = "needs_review"
    else:
        verdict = "passed"
    return {
        "provider": security.get("provider"),
        "model": security.get("model"),
        "verdict": verdict,
        "request_category": category,
        "category_confidence": (answers.get("request_category") or {}).get("confidence"),
        "malicious_probability": (answers.get("malicious_probability") or {}).get("noul"),
        "block_probability": (answers.get("block_probability") or {}).get("noul"),
        "needs_human_review": (answers.get("needs_human_review") or {}).get("noul"),
    }



def _blocked_artifact(task: str, security: dict | None) -> dict:
    snapshot = _security_snapshot(security) or {}
    category = (snapshot.get("request_category") or "unsafe_request").replace("_", " ")
    return {
        "title": "Security review — request blocked",
        "summary": "Service Desk stopped this request before searching documents or writing an answer because it may break the rules or expose private information.",
        "sections": [
            {
                "heading": "Why it was blocked",
                "body": f"The request was classified as {category}. The local guard is designed to stop jailbreak, prompt-injection, policy-evasion and data-exfiltration attempts before they reach the generative model.",
                "citations": [],
            },
            {
                "heading": "What was protected",
                "body": "No protected business write was attempted. No approval rule was bypassed. No hidden prompt, credential, or unrelated private data was exposed.",
                "citations": [],
            },
            {
                "heading": "How to continue safely",
                "body": "Rewrite the request as a normal operational task, or ask an approver or administrator to review it if the task is legitimate but was flagged conservatively.",
                "citations": [],
            },
        ],
        "next_steps": [
            "Remove any instruction that tries to override safety or approval rules.",
            "Ask for the operational outcome you need instead of requesting hidden prompts or bypass behavior.",
            "Escalate to a reviewer if the request was blocked by mistake.",
        ],
        "citations": [],
        "security_signals": snapshot,
        "blocked_task": task,
        "action_proposal": None,
    }



def run_investigation(
    db: Session,
    work: WorkItem,
    user_id: int,
    scopes: list[str],
    task: str,
) -> tuple[Run, dict, list[dict], int | None]:
    run = Run(
        organization_id=work.organization_id,
        work_item_id=work.id,
        requested_by_user_id=user_id,
        status="running",
        task=task,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    work_dict = {
        "id": work.id,
        "title": work.title,
        "customer_name": work.customer_name,
        "asset_ref": work.asset_ref,
        "status": work.status,
        "context": work.context,
    }

    security = assess_request_security(task, work_dict)
    if security:
        snapshot = _security_snapshot(security)
        _event(db, work.organization_id, run.id, "security", "Evaluating prompt risk with local request guard", {
            "provider": security.get("provider"),
            "model": security.get("model"),
            **(snapshot or {}),
        })
    if should_block_request(security):
        _event(db, work.organization_id, run.id, "security", "Blocked risky request before retrieval and generation", {
            "reason": (security or {}).get("routing", {}).get("reason"),
        })
        run.status = "blocked"
        run.provider = (security or {}).get("provider")
        run.model = (security or {}).get("model")
        run.route_reason = (security or {}).get("routing", {}).get("reason")
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        return run, _blocked_artifact(task, security), [], None

    def knowledge_node(state: InvestigationState):
        _event(db, work.organization_id, run.id, "retrieval", "Searching permitted service knowledge")
        evidence = retrieve(db, work.organization_id, scopes, f"{task} {work.customer_name} {work.asset_ref}")
        _event(db, work.organization_id, run.id, "retrieval", f"Retrieved {len(evidence)} permitted source passages", {"source_ids": [e["id"] for e in evidence]})
        return {"evidence": evidence, "sensitivity": max_sensitivity(evidence)}

    def operations_node(state: InvestigationState):
        _event(db, work.organization_id, run.id, "tool", "Querying service history, asset state and parts inventory")
        operations = get_operations_context(db, work.organization_id, work.customer_name, work.asset_ref)
        counts = {"service_cases": len(operations.get("service_cases", [])), "parts": len(operations.get("parts", []))}
        _event(db, work.organization_id, run.id, "tool", "Loaded structured operational context", counts)
        return {"operations": operations}

    def decision_node(state: InvestigationState):
        decisions = score_case(task, work_dict, state.get("evidence", []), state.get("operations", {}))
        if decisions:
            answers = decisions.get("answers", {})
            case_type = (answers.get("case_type") or {}).get("choice")
            priority = (answers.get("priority") or {}).get("score")
            onsite = (answers.get("onsite_inspection") or {}).get("noul")
            label = "Scored operational decision signals"
            if decisions.get("provider") == "laya":
                label = "Scored operational decision signals with local Laya"
            _event(db, work.organization_id, run.id, "decision", label, {
                "provider": decisions.get("provider"),
                "model": decisions.get("model"),
                "case_type": case_type,
                "priority_score": priority,
                "onsite_probability": onsite,
                "note": "Decision signals support triage only; they do not authorize business actions.",
            })
        return {"decisions": decisions}

    def route_node(state: InvestigationState):
        route = route_model(db, work.organization_id, state.get("sensitivity", "internal"))
        _event(db, work.organization_id, run.id, "model", f'Using {route["provider"]} / {route["model"]}', {"reason": route["route_reason"]})
        return {"route": route}

    def compose_node(state: InvestigationState):
        result = generate_briefing(
            state["route"],
            task,
            work_dict,
            state.get("evidence", []),
            state.get("operations", {}),
            state.get("decisions"),
        )
        artifact = sanitize_citations(result["artifact"], {e["id"] for e in state.get("evidence", [])})
        artifact["security_signals"] = _security_snapshot(security)
        result["artifact"] = artifact
        _event(db, work.organization_id, run.id, "artifact", "Created evidence-backed escalation brief", {"citations": artifact.get("citations", [])})
        return {"result": result}

    def proposal_node(state: InvestigationState):
        proposal = state["result"]["artifact"].get("action_proposal")
        if not proposal or proposal.get("type") != "create_work_order":
            return {"action_id": None}
        operations = state.get("operations", {})
        asset = operations.get("asset")
        customer = operations.get("customer")
        if not asset or not customer:
            return {"action_id": None}
        payload = {
            "customer_id": customer["id"],
            "asset_id": asset["id"],
            "asset_ref": asset["asset_ref"],
            "summary": proposal.get("summary", "Service inspection"),
            "requested_work": proposal.get("requested_work", "Inspect asset"),
            "expected_work_status": work.status,
        }
        action = Action(
            organization_id=work.organization_id,
            work_item_id=work.id,
            run_id=run.id,
            type="create_work_order",
            status="pending",
            payload=payload,
            evidence_ids=proposal.get("evidence_ids", []),
            proposed_by_user_id=user_id,
        )
        db.add(action)
        db.commit()
        db.refresh(action)
        _event(db, work.organization_id, run.id, "action", "Prepared a service work-order proposal; approval required", {"action_id": action.id})
        return {"action_id": action.id}

    graph = StateGraph(InvestigationState)
    graph.add_node("knowledge", knowledge_node)
    graph.add_node("operations", operations_node)
    graph.add_node("decision", decision_node)
    graph.add_node("route", route_node)
    graph.add_node("compose", compose_node)
    graph.add_node("proposal", proposal_node)
    graph.set_entry_point("knowledge")
    graph.add_edge("knowledge", "operations")
    graph.add_edge("operations", "decision")
    graph.add_edge("decision", "route")
    graph.add_edge("route", "compose")
    graph.add_edge("compose", "proposal")
    graph.add_edge("proposal", END)

    try:
        final = graph.compile().invoke({"security": security})
        result = final["result"]
        route = final["route"]
        run.status = "completed"
        run.provider = route["provider"]
        run.model = route["model"]
        run.route_reason = route["route_reason"]
        run.latency_ms = result.get("latency_ms")
        run.input_tokens = result.get("input_tokens")
        run.output_tokens = result.get("output_tokens")
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        return run, result["artifact"], final.get("evidence", []), final.get("action_id")
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)[:2000]
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        _event(db, work.organization_id, run.id, "error", "Investigation failed", {"error": str(exc)[:500]})
        raise
