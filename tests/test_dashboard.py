from __future__ import annotations

from httpx import AsyncClient


async def test_login_required_redirect(client: AsyncClient) -> None:
    r = await client.get("/dashboard/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].endswith("/dashboard/login")


async def test_dashboard_login_form(client: AsyncClient) -> None:
    r = await client.get("/dashboard/login")
    assert r.status_code == 200
    assert "Sign in" in r.text


async def test_dashboard_login_and_overview(client: AsyncClient) -> None:
    r = await client.post(
        "/dashboard/login",
        data={"username": "alice", "password": "secret"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"].endswith("/dashboard/")

    r = await client.get("/dashboard/")
    assert r.status_code == 200
    assert "Overview" in r.text
    assert "alice" in r.text


async def test_dashboard_users_create_and_delete(client: AsyncClient) -> None:
    await client.post(
        "/dashboard/login",
        data={"username": "alice", "password": "secret"},
    )
    r = await client.post(
        "/dashboard/users",
        data={"username": "bob", "password": "pw", "email": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303

    r = await client.get("/dashboard/users")
    assert "bob" in r.text

    r = await client.post(
        "/dashboard/users/bob/delete", follow_redirects=False
    )
    assert r.status_code == 303
    r = await client.get("/dashboard/users")
    assert "bob" not in r.text


async def test_admin_username_filter(client: AsyncClient, app) -> None:
    # configure admin_usernames to a non-existent user; alice logs in as
    # a regular user and is redirected to the personal dashboard.
    app.state.gpodder_config.admin_usernames = ["nobody"]
    r = await client.post(
        "/dashboard/login",
        data={"username": "alice", "password": "secret"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"].endswith("/dashboard/me/")
    # admin pages stay protected
    r = await client.get("/dashboard/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].endswith("/dashboard/login")
    # personal dashboard accessible
    r = await client.get("/dashboard/me/")
    assert r.status_code == 200
    assert "alice" in r.text
    app.state.gpodder_config.admin_usernames = []
