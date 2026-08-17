from sqlalchemy import update
from app.db import SessionLocal
from app.models import WorkItem
from app.api.work import SECURITY_DEMO_TASK
from .helpers import login


def work_id(client) -> int:
    return client.get("/api/work").json()["items"][0]["id"]


def investigate(client, wid: int, content: str | None = None) -> dict:
    task = content or client.get("/api/work").json()["demo_task"]
    r = client.post(f"/api/work/{wid}/messages", json={"content": task})
    assert r.status_code == 200, r.text
    return r.json()


def last_message(client, wid: int) -> dict:
    return [m for m in client.get(f"/api/work/{wid}").json()["messages"] if m["role"] == "assistant"][-1]


def test_health_endpoints(client):
    assert client.get("/health").json()["status"] == "ok"
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"


def test_login_success_sets_cookie(client):
    r = login(client, "service@demo.local")
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "service@demo.local"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["organization"] == "Oriole Packaging Systems"


def test_login_options_report_demo_accounts(client):
    assert client.get("/api/auth/options").json() == {"demo": True}


def test_login_wrong_password(client):
    assert login(client, "service@demo.local", "nope").status_code == 401


def test_unauthenticated_work_is_401(client):
    assert client.get("/api/work").status_code == 401


def test_engineer_sees_work_and_finance_does_not(as_user):
    items = as_user("service@demo.local").get("/api/work").json()["items"]
    assert any(i["asset_ref"] == "NSF-PX400-L4" for i in items)
    assert as_user("finance@demo.local").get("/api/work").json()["items"] == []


def test_finance_cannot_list_service_documents(as_user):
    docs = as_user("finance@demo.local").get("/api/sources").json()["documents"]
    assert docs and {d["access_scope"] for d in docs} == {"finance"}
    eng = {d["access_scope"] for d in as_user("service@demo.local").get("/api/sources").json()["documents"]}
    assert "service" in eng and "finance" not in eng


def test_investigation_completes_with_valid_citations_and_pending_action(as_user):
    c = as_user("service@demo.local")
    wid = work_id(c)
    result = investigate(c, wid)
    assert c.get(f"/api/runs/{result['run_id']}").json()["run"]["status"] == "completed"
    meta = last_message(c, wid)["meta"]
    evidence_ids = {e["id"] for e in meta["evidence"]}
    assert evidence_ids
    citations = set(meta["artifact"]["citations"])
    assert citations and citations <= evidence_ids
    action = c.get(f"/api/actions/{result['action_id']}").json()["action"]
    assert action["type"] == "create_work_order" and action["status"] == "pending"


def test_prompt_injection_is_blocked(as_user):
    c = as_user("service@demo.local")
    wid = work_id(c)
    result = investigate(c, wid, SECURITY_DEMO_TASK)
    assert result["action_id"] is None
    assert c.get(f"/api/runs/{result['run_id']}").json()["run"]["status"] == "blocked"
    assert last_message(c, wid)["meta"]["evidence"] == []
    assert c.get("/api/actions").json()["items"] == []


def test_engineer_cannot_approve(as_user):
    eng = as_user("service@demo.local")
    result = investigate(eng, work_id(eng))
    assert eng.post(f"/api/actions/{result['action_id']}/approve").status_code == 403


def test_manager_approves_once(as_user):
    eng, mgr = as_user("service@demo.local"), as_user("manager@demo.local")
    aid = investigate(eng, work_id(eng))["action_id"]
    r = mgr.post(f"/api/actions/{aid}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "executed" and r.json()["work_order_ref"].startswith("WO-")
    assert mgr.post(f"/api/actions/{aid}/approve").status_code == 409


def test_stale_proposal_cannot_be_approved(as_user):
    eng, mgr = as_user("service@demo.local"), as_user("manager@demo.local")
    wid = work_id(eng)
    aid = investigate(eng, wid)["action_id"]
    with SessionLocal() as db:
        db.execute(update(WorkItem).where(WorkItem.id == wid).values(status="in_progress"))
        db.commit()
    assert mgr.post(f"/api/actions/{aid}/approve").status_code == 409
    assert mgr.get(f"/api/actions/{aid}").json()["action"]["status"] == "stale"


def test_reset_demo_forbidden_for_engineer(as_user):
    assert as_user("service@demo.local").post("/api/admin/reset-demo").status_code == 403


def test_created_user_signs_in_to_their_own_organization(client):
    from app.manage import create_user
    create_user("lead@example.test", "Service Lead", "approver", ["service"], "Example Industries", "a-long-test-password")
    assert login(client, "lead@example.test", "a-long-test-password").status_code == 200
    assert client.get("/api/auth/me").json()["user"]["organization"] == "Example Industries"
    assert client.get("/api/work").json()["items"] == []
    assert client.get("/api/sources").json()["documents"] == []
