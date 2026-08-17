#!/usr/bin/env python3
import json
import urllib.request
import http.cookiejar

BASE = "http://localhost:8000"
TASK = "Prepare tomorrow's escalation brief for Northstar Foods. Check the maintenance agreement, previous service history, relevant E-217 troubleshooting guidance and parts availability. Recommend next steps and prepare a service work order if the evidence supports one."


def client():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(opener, method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with opener.open(req, timeout=90) as response:
        return json.loads(response.read())


engineer = client()
call(engineer, "POST", "/api/auth/login", {"email": "service@demo.local", "password": "demo-password"})
work = call(engineer, "GET", "/api/work")
assert work["items"], "seeded work item missing"
work_id = work["items"][0]["id"]
result = call(engineer, "POST", f"/api/work/{work_id}/messages", {"content": TASK})
assert result["run_id"]
assert result["action_id"], "demo investigation did not create action proposal"

actions = call(engineer, "GET", "/api/actions")
pending = next((x for x in actions["items"] if x["id"] == result["action_id"]), None)
assert pending and pending["status"] == "pending"

manager = client()
call(manager, "POST", "/api/auth/login", {"email": "manager@demo.local", "password": "demo-password"})
approved = call(manager, "POST", f"/api/actions/{result['action_id']}/approve")
assert approved["status"] == "executed"
print(f"smoke OK: work={work_id} run={result['run_id']} action={result['action_id']} work_order={approved['work_order_ref']}")
