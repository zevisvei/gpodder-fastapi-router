from __future__ import annotations

from httpx import AsyncClient


async def test_update_and_list_device(client: AsyncClient, alice_auth: dict[str, str]) -> None:
    r = await client.post(
        "/api/2/devices/alice/phone.json",
        json={"caption": "My Phone", "type": "mobile"},
        headers=alice_auth,
    )
    assert r.status_code == 200

    r = await client.get("/api/2/devices/alice.json", headers=alice_auth)
    assert r.status_code == 200
    payload = r.json()
    assert any(d["id"] == "phone" and d["caption"] == "My Phone" for d in payload)


async def test_device_updates_empty(client: AsyncClient, alice_auth: dict[str, str]) -> None:
    r = await client.get(
        "/api/2/updates/alice/phone.json?since=0", headers=alice_auth
    )
    assert r.status_code == 200
    body = r.json()
    assert body["add"] == []
    assert body["rem"] == []
    assert "timestamp" in body
