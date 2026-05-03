from __future__ import annotations

from httpx import AsyncClient


async def test_full_upload_and_get(client: AsyncClient, alice_auth: dict[str, str]) -> None:
    urls = ["https://a.example/feed.xml", "https://b.example/feed.xml"]
    r = await client.put(
        "/subscriptions/alice/phone.json", json=urls, headers=alice_auth
    )
    assert r.status_code == 200

    r = await client.get("/subscriptions/alice/phone.json", headers=alice_auth)
    assert r.status_code == 200
    assert sorted(r.json()) == sorted(urls)

    # txt format round-trip
    r = await client.get("/subscriptions/alice/phone.txt", headers=alice_auth)
    assert r.status_code == 200
    lines = [l for l in r.text.splitlines() if l]
    assert sorted(lines) == sorted(urls)

    # opml format
    r = await client.get("/subscriptions/alice/phone.opml", headers=alice_auth)
    assert r.status_code == 200
    assert "<opml" in r.text
    assert "a.example" in r.text


async def test_changes_diff_and_replay(
    client: AsyncClient, alice_auth: dict[str, str]
) -> None:
    r = await client.post(
        "/api/2/subscriptions/alice/phone.json",
        json={"add": ["https://x.example/f"], "remove": []},
        headers=alice_auth,
    )
    assert r.status_code == 200
    ts1 = r.json()["timestamp"]

    r = await client.post(
        "/api/2/subscriptions/alice/phone.json",
        json={"add": ["https://y.example/f"], "remove": ["https://x.example/f"]},
        headers=alice_auth,
    )
    assert r.status_code == 200

    r = await client.get(
        f"/api/2/subscriptions/alice/phone.json?since={ts1 - 1}",
        headers=alice_auth,
    )
    assert r.status_code == 200
    body = r.json()
    assert "https://y.example/f" in body["add"] or "https://x.example/f" in body["add"]


async def test_sync_group_propagates_changes(
    client: AsyncClient, alice_auth: dict[str, str]
) -> None:
    # register both devices
    for dev in ("phone", "laptop"):
        await client.post(
            f"/api/2/devices/alice/{dev}.json",
            json={"type": "mobile"},
            headers=alice_auth,
        )
    # group them
    r = await client.post(
        "/api/2/sync-devices/alice.json",
        json={"synchronize": [["phone", "laptop"]], "stop-synchronize": []},
        headers=alice_auth,
    )
    assert r.status_code == 200

    r = await client.post(
        "/api/2/subscriptions/alice/phone.json",
        json={"add": ["https://shared.example/f"], "remove": []},
        headers=alice_auth,
    )
    assert r.status_code == 200

    # laptop sees the same subscription via /subscriptions and /api/2/subscriptions
    r = await client.get("/subscriptions/alice/laptop.json", headers=alice_auth)
    assert r.status_code == 200
    assert "https://shared.example/f" in r.json()

    r = await client.get(
        "/api/2/subscriptions/alice/laptop.json?since=0", headers=alice_auth
    )
    assert r.status_code == 200
    assert "https://shared.example/f" in r.json()["add"]


async def test_subscription_normalizes_url(
    client: AsyncClient, alice_auth: dict[str, str]
) -> None:
    r = await client.post(
        "/api/2/subscriptions/alice/phone.json",
        json={"add": ["HTTP://Example.COM/feed"], "remove": []},
        headers=alice_auth,
    )
    assert r.status_code == 200
    pairs = r.json()["update_urls"]
    assert any(orig == "HTTP://Example.COM/feed" and norm == "http://example.com/feed"
               for orig, norm in pairs)
    r = await client.get("/subscriptions/alice/phone.json", headers=alice_auth)
    assert "http://example.com/feed" in r.json()


async def test_subscription_add_remove_conflict(
    client: AsyncClient, alice_auth: dict[str, str]
) -> None:
    """mygpo returns 400 when the same URL appears in both add and remove."""
    r = await client.post(
        "/api/2/subscriptions/alice/phone.json",
        json={"add": ["https://a.example/f"], "remove": ["https://a.example/f"]},
        headers=alice_auth,
    )
    assert r.status_code == 400


async def test_all_user_subscriptions(client: AsyncClient, alice_auth: dict[str, str]) -> None:
    await client.put(
        "/subscriptions/alice/phone.json",
        json=["https://one.example/f"],
        headers=alice_auth,
    )
    await client.put(
        "/subscriptions/alice/laptop.json",
        json=["https://two.example/f"],
        headers=alice_auth,
    )
    r = await client.get("/subscriptions/alice.json", headers=alice_auth)
    assert r.status_code == 200
    assert sorted(r.json()) == ["https://one.example/f", "https://two.example/f"]
