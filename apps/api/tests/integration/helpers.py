from fastapi.testclient import TestClient

PASSWORD = "demo-password"


def login(client: TestClient, email: str, password: str = PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})
