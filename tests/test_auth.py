from __future__ import annotations

from httpx import AsyncClient


async def test_login_ok(client: AsyncClient, alice_auth: dict[str, str]) -> None:
    r = await client.post("/api/2/auth/alice/login.json", headers=alice_auth)
    assert r.status_code == 200


async def test_login_bad_password(client: AsyncClient, bad_auth: dict[str, str]) -> None:
    r = await client.post("/api/2/auth/alice/login.json", headers=bad_auth)
    assert r.status_code == 401


async def test_login_username_mismatch(client: AsyncClient, alice_auth: dict[str, str]) -> None:
    r = await client.post("/api/2/auth/bob/login.json", headers=alice_auth)
    assert r.status_code == 400


async def test_logout(client: AsyncClient, alice_auth: dict[str, str]) -> None:
    r = await client.post("/api/2/auth/alice/logout.json", headers=alice_auth)
    assert r.status_code == 200


async def test_logout_without_auth(client: AsyncClient) -> None:
    """mygpo's logout endpoint requires no authentication; ours must match."""
    r = await client.post("/api/2/auth/alice/logout.json")
    assert r.status_code == 200


async def test_register_creates_user(client: AsyncClient) -> None:
    r = await client.post(
        "/api/2/auth/charlie/register.json", json={"password": "pw"}
    )
    assert r.status_code == 201


async def test_register_conflict(client: AsyncClient) -> None:
    r = await client.post(
        "/api/2/auth/alice/register.json", json={"password": "pw"}
    )
    assert r.status_code == 409
