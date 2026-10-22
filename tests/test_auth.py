"""Registration and login hardening."""
import main


async def test_only_known_employees_can_register(client, db):
    r = await client.post("/api/register", json={"employee_code": "GHOST1", "password": "Pass1234!"})
    assert r.status_code == 400
    await db["user"].delete_many({"employee_code": "EMP001"})
    r = await client.post("/api/register", json={"employee_code": "EMP001", "password": "Pass1234!"})
    assert r.status_code == 200
    r = await client.post("/api/login", json={"employee_code": "EMP001", "password": "Pass1234!"})
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"


async def test_login_is_throttled_after_repeated_failures(client, db):
    main._login_failures.clear()
    await db["user"].delete_many({"employee_code": "EMP002"})
    await client.post("/api/register", json={"employee_code": "EMP002", "password": "Right-pass1"})
    for _ in range(8):
        r = await client.post("/api/login", json={"employee_code": "EMP002", "password": "wrong"})
        assert r.status_code == 401
    r = await client.post("/api/login", json={"employee_code": "EMP002", "password": "Right-pass1"})
    assert r.status_code == 429
    main._login_failures.clear()
    r = await client.post("/api/login", json={"employee_code": "EMP002", "password": "Right-pass1"})
    assert r.status_code == 200


async def test_security_headers_present(client, db):
    r = await client.get("/login.html")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
