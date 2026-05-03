from __future__ import annotations

from httpx import AsyncClient


async def test_account_settings(client: AsyncClient, alice_auth: dict[str, str]) -> None:
    r = await client.post(
        "/api/2/settings/alice/account.json",
        json={"set": {"theme": "dark", "lang": "he"}, "remove": []},
        headers=alice_auth,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["theme"] == "dark"
    assert body["lang"] == "he"

    r = await client.post(
        "/api/2/settings/alice/account.json",
        json={"set": {}, "remove": ["theme"]},
        headers=alice_auth,
    )
    assert r.status_code == 200
    assert "theme" not in r.json()


async def test_podcast_scope_requires_podcast(
    client: AsyncClient, alice_auth: dict[str, str]
) -> None:
    r = await client.get(
        "/api/2/settings/alice/podcast.json", headers=alice_auth
    )
    assert r.status_code == 404


async def test_lists_create_get_update_delete(
    client: AsyncClient, alice_auth: dict[str, str]
) -> None:
    r = await client.post(
        "/api/2/lists/alice/create.json?title=My Faves",
        json=["https://a.example/f"],
        headers=alice_auth,
    )
    assert r.status_code == 201
    assert r.content == b""
    location = r.headers["location"]
    assert location.startswith("/api/2/lists/alice/list/")
    assert location.endswith(".json")
    name = location.split("/list/")[1].rsplit(".json", 1)[0]

    r = await client.get(f"/api/2/lists/alice/list/{name}.json")
    assert r.status_code == 200
    assert r.json() == ["https://a.example/f"]

    r = await client.put(
        f"/api/2/lists/alice/list/{name}.json",
        json=["https://a.example/f", "https://b.example/f"],
        headers=alice_auth,
    )
    assert r.status_code == 204

    r = await client.get(f"/api/2/lists/alice/list/{name}.opml")
    assert r.status_code == 200
    assert "b.example" in r.text

    r = await client.delete(
        f"/api/2/lists/alice/list/{name}.json", headers=alice_auth
    )
    assert r.status_code == 204


async def test_sync_groups_unknown_device_404(
    client: AsyncClient, alice_auth: dict[str, str]
) -> None:
    r = await client.post(
        "/api/2/sync-devices/alice.json",
        json={"synchronize": [["ghost-a", "ghost-b"]], "stop-synchronize": []},
        headers=alice_auth,
    )
    assert r.status_code == 404


async def test_sync_groups_singleton_400(
    client: AsyncClient, alice_auth: dict[str, str]
) -> None:
    await client.post(
        "/api/2/devices/alice/phone.json",
        json={"type": "mobile"},
        headers=alice_auth,
    )
    r = await client.post(
        "/api/2/sync-devices/alice.json",
        json={"synchronize": [["phone"]], "stop-synchronize": []},
        headers=alice_auth,
    )
    assert r.status_code == 400


async def test_sync_groups(client: AsyncClient, alice_auth: dict[str, str]) -> None:
    # ensure devices exist
    for dev in ("phone", "laptop", "tablet"):
        await client.post(
            f"/api/2/devices/alice/{dev}.json",
            json={"type": "mobile"},
            headers=alice_auth,
        )

    r = await client.post(
        "/api/2/sync-devices/alice.json",
        json={"synchronize": [["phone", "laptop"]], "stop-synchronize": []},
        headers=alice_auth,
    )
    assert r.status_code == 200
    body = r.json()
    assert ["laptop", "phone"] in body["synchronized"]
    assert "tablet" in body["not-synchronized"]

    r = await client.post(
        "/api/2/sync-devices/alice.json",
        json={"synchronize": [], "stop-synchronize": ["laptop"]},
        headers=alice_auth,
    )
    assert r.status_code == 200
    assert r.json()["synchronized"] == []


async def test_clientconfig(client: AsyncClient) -> None:
    r = await client.get("/clientconfig.json")
    assert r.status_code == 200
    body = r.json()
    assert "mygpo" in body
    assert "mygpo-feedservice" in body
    assert "update_timeout" in body
