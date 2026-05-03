from __future__ import annotations

from httpx import AsyncClient


async def test_upload_and_get_actions(client: AsyncClient, alice_auth: dict[str, str]) -> None:
    payload = [
        {
            "podcast": "https://p.example/feed",
            "episode": "https://p.example/ep1.mp3",
            "device": "phone",
            "action": "play",
            "timestamp": "2026-01-01T00:00:00",
            "started": 0,
            "position": 42,
            "total": 100,
        }
    ]
    r = await client.post(
        "/api/2/episodes/alice.json", json=payload, headers=alice_auth
    )
    assert r.status_code == 200
    assert "timestamp" in r.json()

    r = await client.get(
        "/api/2/episodes/alice.json?podcast=https://p.example/feed",
        headers=alice_auth,
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["actions"]) == 1
    assert body["actions"][0]["action"] == "play"
    assert body["actions"][0]["position"] == 42


async def test_action_guid_roundtrip(
    client: AsyncClient, alice_auth: dict[str, str]
) -> None:
    payload = [
        {
            "podcast": "https://p.example/feed",
            "episode": "https://p.example/ep.mp3",
            "guid": "abc-123-guid",
            "device": "phone",
            "action": "play",
            "timestamp": "2026-01-01T00:00:00",
            "started": 0,
            "position": 5,
            "total": 10,
        }
    ]
    r = await client.post("/api/2/episodes/alice.json", json=payload, headers=alice_auth)
    assert r.status_code == 200
    r = await client.get(
        "/api/2/episodes/alice.json?podcast=https://p.example/feed", headers=alice_auth
    )
    assert r.status_code == 200
    actions = r.json()["actions"]
    assert actions[0]["guid"] == "abc-123-guid"


async def test_upload_normalizes_urls(
    client: AsyncClient, alice_auth: dict[str, str]
) -> None:
    payload = [
        {
            "podcast": "HTTPS://P.Example/feed",
            "episode": "HTTPS://USER:PASS@P.Example/ep.mp3",
            "device": "phone",
            "action": "download",
        }
    ]
    r = await client.post("/api/2/episodes/alice.json", json=payload, headers=alice_auth)
    assert r.status_code == 200
    body = r.json()
    rewrites = {orig: norm for orig, norm in body["update_urls"]}
    assert rewrites["HTTPS://P.Example/feed"] == "https://p.example/feed"
    assert rewrites["HTTPS://USER:PASS@P.Example/ep.mp3"] == "https://p.example/ep.mp3"


async def test_get_actions_unknown_device_404(
    client: AsyncClient, alice_auth: dict[str, str]
) -> None:
    r = await client.get(
        "/api/2/episodes/alice.json?device=ghost", headers=alice_auth
    )
    assert r.status_code == 404


async def test_get_actions_response_timestamp_is_last_action_ts(
    client: AsyncClient, alice_auth: dict[str, str]
) -> None:
    payload = [
        {
            "podcast": "https://p.example/feed",
            "episode": "https://p.example/ep.mp3",
            "action": "play",
            "timestamp": "2026-01-15T10:00:00",
            "started": 0,
            "position": 5,
            "total": 10,
        }
    ]
    r = await client.post("/api/2/episodes/alice.json", json=payload, headers=alice_auth)
    assert r.status_code == 200

    r = await client.get(
        "/api/2/episodes/alice.json?podcast=https://p.example/feed", headers=alice_auth
    )
    body = r.json()
    # 2026-01-15T10:00:00Z = 1768471200
    assert body["timestamp"] == 1768471200


async def test_get_actions_since_filter_uses_action_timestamp(
    client: AsyncClient, alice_auth: dict[str, str]
) -> None:
    base = {
        "podcast": "https://p.example/feed",
        "episode": "https://p.example/ep.mp3",
        "action": "play",
        "started": 0,
        "position": 5,
        "total": 10,
    }
    await client.post(
        "/api/2/episodes/alice.json",
        json=[{**base, "timestamp": "2026-01-01T00:00:00"}],
        headers=alice_auth,
    )
    await client.post(
        "/api/2/episodes/alice.json",
        json=[{**base, "timestamp": "2026-06-01T00:00:00"}],
        headers=alice_auth,
    )
    # 2026-03-01T00:00:00Z = 1772582400 — should exclude the January action.
    r = await client.get(
        "/api/2/episodes/alice.json?podcast=https://p.example/feed&since=1772582400",
        headers=alice_auth,
    )
    actions = r.json()["actions"]
    assert len(actions) == 1
    assert actions[0]["timestamp"] == "2026-06-01T00:00:00"


async def test_actions_aggregated(client: AsyncClient, alice_auth: dict[str, str]) -> None:
    base = {
        "podcast": "https://p.example/feed",
        "episode": "https://p.example/ep.mp3",
        "device": "phone",
    }
    for pos in (10, 20, 30):
        await client.post(
            "/api/2/episodes/alice.json",
            json=[{**base, "action": "play", "position": pos}],
            headers=alice_auth,
        )
    r = await client.get(
        "/api/2/episodes/alice.json?podcast=https://p.example/feed&aggregated=true",
        headers=alice_auth,
    )
    assert r.status_code == 200
    actions = r.json()["actions"]
    assert len(actions) == 1
    assert actions[0]["position"] == 30
