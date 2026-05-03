from __future__ import annotations

from httpx import AsyncClient


async def test_login_sets_cookie_and_cookie_authenticates(
    client: AsyncClient, alice_auth: dict[str, str]
) -> None:
    r = await client.post("/api/2/auth/alice/login.json", headers=alice_auth)
    assert r.status_code == 200
    assert "sessionid" in r.cookies

    # subsequent request without Basic auth, only the cookie
    r2 = await client.get("/api/2/devices/alice.json")
    assert r2.status_code == 200


async def test_logout_invalidates_cookie(
    client: AsyncClient, alice_auth: dict[str, str]
) -> None:
    await client.post("/api/2/auth/alice/login.json", headers=alice_auth)
    r = await client.post("/api/2/auth/alice/logout.json")
    assert r.status_code == 200

    # cookie cleared, no Basic auth -> 401
    client.cookies.clear()
    r = await client.get("/api/2/devices/alice.json")
    assert r.status_code == 401
