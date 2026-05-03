from __future__ import annotations

from pathlib import Path as _Path
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from gpodder_router.dashboard.auth import AdminDep, UserDep, is_admin
from gpodder_router.db import (
    Device,
    EpisodeAction,
    Favorite,
    PodcastList,
    Subscription,
    User,
)
from gpodder_router.deps import SESSION_COOKIE, ConfigDep, SessionDep
from gpodder_router.exceptions import NotFoundError
from gpodder_router.security import verify_password
from gpodder_router.services import discover as discover_service
from gpodder_router.services import feeds as feed_service
from gpodder_router.services import sessions as session_service
from gpodder_router.services import subscriptions as subscription_service
from gpodder_router.services import users as user_service

_HERE = _Path(__file__).parent
_TEMPLATES = Jinja2Templates(directory=str(_HERE / "templates"))


def _fmt_ts(value) -> str:
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return ""
    if ts <= 0:
        return ""
    import datetime as _dt

    return _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _fmt_duration(value) -> str:
    if not value:
        return ""
    s = str(value).strip()
    if ":" in s:
        return s
    try:
        secs = int(s)
    except ValueError:
        return s
    h, rem = divmod(secs, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


from urllib.parse import quote as _urlquote


def _fmt_iso(value) -> str:
    if not value:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    import datetime as _dt

    dt: _dt.datetime | None = None
    for candidate in (s, s.replace("Z", "+00:00")):
        try:
            dt = _dt.datetime.fromisoformat(candidate)
            break
        except ValueError:
            continue
    if dt is None:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = _dt.datetime.strptime(s[:19], fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return s
    if dt.tzinfo is None:
        # AntennaPod sends UTC without TZ suffix; treat naive as UTC
        dt = dt.replace(tzinfo=_dt.UTC)
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


_TEMPLATES.env.filters["fmt_ts"] = _fmt_ts
_TEMPLATES.env.filters["fmt_duration"] = _fmt_duration
_TEMPLATES.env.filters["fmt_iso"] = _fmt_iso
_TEMPLATES.env.filters["urlencode_q"] = lambda v: _urlquote(str(v or ""), safe="")


def build_dashboard_router(prefix: str = "/dashboard") -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["Dashboard"], include_in_schema=False)

    static_dir = _HERE / "static"
    if static_dir.is_dir():
        # mount static via a dependency-free route (sub-app would shadow prefix)
        @router.get("/static/{path:path}", include_in_schema=False)
        async def _static(path: str) -> Response:
            file_path = (static_dir / path).resolve()
            if not str(file_path).startswith(str(static_dir.resolve())):
                raise NotFoundError()
            if not file_path.is_file():
                raise NotFoundError()
            data = file_path.read_bytes()
            mime = "text/css" if path.endswith(".css") else "application/octet-stream"
            return Response(content=data, media_type=mime)

    def _ctx(request: Request, config, **extra) -> dict:
        ctx = {"request": request, "prefix": config.dashboard_prefix, **extra}
        if "is_admin" not in ctx:
            ctx["is_admin"] = "admin" in extra
        return ctx

    @router.get("/login", response_class=HTMLResponse)
    async def login_form(request: Request, config: ConfigDep) -> Response:
        return _TEMPLATES.TemplateResponse(
            request, "login.html", _ctx(request, config, error=None)
        )

    @router.post("/login")
    async def login_submit(
        request: Request,
        session: SessionDep,
        config: ConfigDep,
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
    ) -> Response:
        user = await user_service.get_user(session, username)
        ok = user is not None and verify_password(password, user.password_hash)
        if not ok:
            return _TEMPLATES.TemplateResponse(
                request,
                "login.html",
                _ctx(request, config, error="Invalid credentials"),
                status_code=400,
            )
        admin_user = await is_admin(config, session, user.username)
        token = await session_service.create_session(session, user)
        target = "/" if admin_user else "/me/"
        resp = RedirectResponse(config.dashboard_prefix + target, status_code=303)
        resp.set_cookie(
            SESSION_COOKIE, token, httponly=True, samesite="lax", path="/",
            max_age=session_service.DEFAULT_TTL,
        )
        return resp

    @router.get("/logout")
    async def logout(
        session: SessionDep,
        config: ConfigDep,
        sessionid: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        if sessionid:
            await session_service.revoke(session, sessionid)
        resp = RedirectResponse(config.dashboard_prefix + "/login", status_code=303)
        resp.delete_cookie(SESSION_COOKIE, path="/")
        return resp

    @router.get("/", response_class=HTMLResponse)
    async def index(
        request: Request, session: SessionDep, config: ConfigDep, admin: AdminDep
    ) -> Response:
        users = int((await session.scalar(select(func.count(User.id)))) or 0)
        devices = int((await session.scalar(select(func.count(Device.id)))) or 0)
        subs = int(
            (
                await session.scalar(
                    select(func.count(Subscription.id)).where(Subscription.deleted == 0)
                )
            )
            or 0
        )
        actions = int(
            (await session.scalar(select(func.count(EpisodeAction.id)))) or 0
        )
        lists = int((await session.scalar(select(func.count(PodcastList.id)))) or 0)
        return _TEMPLATES.TemplateResponse(
            request,
            "index.html",
            _ctx(
                request,
                config,
                admin=admin,
                stats={
                    "users": users,
                    "devices": devices,
                    "subscriptions": subs,
                    "episode_actions": actions,
                    "podcast_lists": lists,
                },
            ),
        )

    @router.get("/users", response_class=HTMLResponse)
    async def users_list(
        request: Request, session: SessionDep, config: ConfigDep, admin: AdminDep
    ) -> Response:
        rows = list((await session.scalars(select(User).order_by(User.id))).all())
        return _TEMPLATES.TemplateResponse(
            request,
            "users.html",
            _ctx(request, config, admin=admin, users=rows, error=None),
        )

    @router.post("/users")
    async def users_create(
        session: SessionDep,
        config: ConfigDep,
        admin: AdminDep,
        request: Request,
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
        email: Annotated[str | None, Form()] = None,
    ) -> Response:
        try:
            await user_service.create_user(
                session,
                username=username.strip(),
                password=password,
                email=(email or None),
                bcrypt_rounds=config.bcrypt_rounds,
            )
        except Exception as exc:  # noqa: BLE001
            rows = list((await session.scalars(select(User).order_by(User.id))).all())
            return _TEMPLATES.TemplateResponse(
                request,
                "users.html",
                _ctx(request, config, admin=admin, users=rows, error=str(exc)),
                status_code=400,
            )
        return RedirectResponse(config.dashboard_prefix + "/users", status_code=303)

    @router.post("/users/{username}/delete")
    async def users_delete(
        username: str,
        session: SessionDep,
        config: ConfigDep,
        admin: AdminDep,
    ) -> Response:
        if username == admin.username:
            return RedirectResponse(
                config.dashboard_prefix + "/users", status_code=303
            )
        target = await user_service.get_user(session, username)
        if target is not None:
            await session.delete(target)
            await session.commit()
        return RedirectResponse(config.dashboard_prefix + "/users", status_code=303)

    @router.post("/users/{username}/password")
    async def users_password(
        username: str,
        session: SessionDep,
        config: ConfigDep,
        admin: AdminDep,
        password: Annotated[str, Form()],
    ) -> Response:
        target = await user_service.get_user(session, username)
        if target is not None and password:
            await user_service.set_password(
                session, target, password, bcrypt_rounds=config.bcrypt_rounds
            )
        return RedirectResponse(config.dashboard_prefix + "/users", status_code=303)

    @router.get("/users/{username}", response_class=HTMLResponse)
    async def user_detail(
        username: str,
        request: Request,
        session: SessionDep,
        config: ConfigDep,
        admin: AdminDep,
    ) -> Response:
        target = await user_service.get_user(session, username)
        if target is None:
            raise NotFoundError(f"user {username!r} not found")
        devices = list(
            (await session.scalars(select(Device).where(Device.user_id == target.id))).all()
        )
        sub_rows = list(
            (
                await session.scalars(
                    select(Subscription).where(
                        Subscription.user_id == target.id, Subscription.deleted == 0
                    )
                )
            ).all()
        )
        action_count = int(
            (
                await session.scalar(
                    select(func.count(EpisodeAction.id)).where(
                        EpisodeAction.user_id == target.id
                    )
                )
            )
            or 0
        )
        return _TEMPLATES.TemplateResponse(
            request,
            "user_detail.html",
            _ctx(
                request,
                config,
                admin=admin,
                user=target,
                devices=devices,
                subscriptions=sub_rows,
                action_count=action_count,
            ),
        )

    @router.get("/me", response_class=HTMLResponse)
    @router.get("/me/", response_class=HTMLResponse)
    async def me_index(
        request: Request, session: SessionDep, config: ConfigDep, user: UserDep
    ) -> Response:
        devices_count = int(
            (
                await session.scalar(
                    select(func.count(Device.id)).where(Device.user_id == user.id)
                )
            )
            or 0
        )
        from sqlalchemy import case as _case

        subs_count_subq = (
            select(
                Subscription.podcast_url,
                func.max(
                    _case((Subscription.deleted == 0, Subscription.created), else_=0)
                ).label("mc"),
                func.max(Subscription.deleted).label("md"),
            )
            .where(Subscription.user_id == user.id)
            .group_by(Subscription.podcast_url)
            .subquery()
        )
        subs_count = int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(subs_count_subq)
                    .where(subs_count_subq.c.mc > func.coalesce(subs_count_subq.c.md, 0))
                )
            )
            or 0
        )
        actions_count = int(
            (
                await session.scalar(
                    select(func.count(EpisodeAction.id)).where(
                        EpisodeAction.user_id == user.id
                    )
                )
            )
            or 0
        )
        fav_count = int(
            (
                await session.scalar(
                    select(func.count(Favorite.id)).where(Favorite.user_id == user.id)
                )
            )
            or 0
        )
        last_action_ts = await session.scalar(
            select(func.max(EpisodeAction.uploaded)).where(
                EpisodeAction.user_id == user.id
            )
        )
        admin_flag = await is_admin(config, session, user.username)
        return _TEMPLATES.TemplateResponse(
            request,
            "me_index.html",
            _ctx(
                request,
                config,
                user=user,
                is_admin=admin_flag,
                stats={
                    "devices": devices_count,
                    "subscriptions": subs_count,
                    "episode_actions": actions_count,
                    "favorites": fav_count,
                    "last_action": int(last_action_ts) if last_action_ts else 0,
                },
            ),
        )

    @router.get("/me/podcasts", response_class=HTMLResponse)
    async def me_podcasts(
        request: Request,
        session: SessionDep,
        config: ConfigDep,
        user: UserDep,
        sort: str = "latest_desc",
        error: str | None = None,
        notice: str | None = None,
    ) -> Response:
        # Active = latest creation across devices is newer than latest deletion.
        # Handles per-device gpodder semantics: if AntennaPod unsubscribed
        # (deletion ts) more recently than any device's last subscribe (creation ts),
        # treat the podcast as inactive across the account.
        from sqlalchemy import case

        max_created = func.max(
            case((Subscription.deleted == 0, Subscription.created), else_=0)
        ).label("max_created")
        max_deleted = func.max(Subscription.deleted).label("max_deleted")
        active_device_count = func.sum(
            case((Subscription.deleted == 0, 1), else_=0)
        ).label("active_device_count")
        rows = list(
            (
                await session.execute(
                    select(
                        Subscription.podcast_url,
                        max_created,
                        max_deleted,
                        active_device_count,
                    )
                    .where(Subscription.user_id == user.id)
                    .group_by(Subscription.podcast_url)
                    .having(max_created > func.coalesce(max_deleted, 0))
                    .order_by(max_created.desc())
                )
            ).all()
        )
        action_counts_rows = (
            await session.execute(
                select(
                    EpisodeAction.podcast_url,
                    func.count(EpisodeAction.id),
                )
                .where(EpisodeAction.user_id == user.id)
                .group_by(EpisodeAction.podcast_url)
            )
        ).all()
        action_counts = {url: int(c) for url, c in action_counts_rows}
        feeds = await feed_service.fetch_many(r.podcast_url for r in rows)
        podcasts = []
        for r in rows:
            feed = feeds.get(r.podcast_url)
            latest_ts = 0
            if feed and feed.episodes:
                latest_ts = max(
                    (ep.pub_ts or 0 for ep in feed.episodes), default=0
                )
            podcasts.append(
                {
                    "url": r.podcast_url,
                    "created": int(r.max_created or 0),
                    "device_count": int(r.active_device_count or 0),
                    "actions": action_counts.get(r.podcast_url, 0),
                    "title": feed.title if feed else r.podcast_url,
                    "image": feed.image if feed else None,
                    "description": feed.description if feed else None,
                    "author": feed.author if feed else None,
                    "link": feed.link if feed else None,
                    "episode_count": len(feed.episodes) if feed else 0,
                    "latest_ts": latest_ts,
                    "error": feed.error if feed else None,
                }
            )
        sort_keys = {
            "latest_desc": (lambda p: p["latest_ts"], True),
            "latest_asc": (lambda p: p["latest_ts"], False),
            "title_asc": (lambda p: p["title"].lower(), False),
            "title_desc": (lambda p: p["title"].lower(), True),
            "episodes_desc": (lambda p: p["episode_count"], True),
            "episodes_asc": (lambda p: p["episode_count"], False),
            "actions_desc": (lambda p: p["actions"], True),
            "actions_asc": (lambda p: p["actions"], False),
            "subscribed_desc": (lambda p: p["created"], True),
            "subscribed_asc": (lambda p: p["created"], False),
        }
        key, reverse = sort_keys.get(sort, sort_keys["latest_desc"])
        podcasts.sort(key=key, reverse=reverse)
        admin_flag = await is_admin(config, session, user.username)
        return _TEMPLATES.TemplateResponse(
            request,
            "me_podcasts.html",
            _ctx(
                request,
                config,
                user=user,
                is_admin=admin_flag,
                podcasts=podcasts,
                sort=sort,
                error=error,
                notice=notice,
            ),
        )

    @router.post("/me/podcasts/subscribe")
    async def me_subscribe(
        session: SessionDep,
        config: ConfigDep,
        user: UserDep,
        url: Annotated[str, Form()],
    ) -> Response:
        clean = (url or "").strip()
        prefix = config.dashboard_prefix
        if not clean or not feed_service._safe_url(clean):
            return RedirectResponse(
                f"{prefix}/me/podcasts?error=invalid+URL", status_code=303
            )
        # Replicate to all user devices so external clients (AntennaPod etc.)
        # pick the new subscription up on next sync. Always include
        # web-dashboard so dashboard-only users still get a device row.
        existing_devices = list(
            (
                await session.scalars(
                    select(Device.deviceid).where(Device.user_id == user.id)
                )
            ).all()
        )
        target_devices = sorted(set(existing_devices) | {"web-dashboard"})
        # If the URL was previously unsubscribed on any device, mark all
        # stale-active rows deleted so apply_changes creates fresh rows
        # whose created ts > the prior deletion. Otherwise the account-level
        # "active" check (max(created) > max(deleted)) keeps it hidden.
        import time as _time

        now_ts = int(_time.time())
        max_del = int(
            (
                await session.scalar(
                    select(func.coalesce(func.max(Subscription.deleted), 0)).where(
                        Subscription.user_id == user.id,
                        Subscription.podcast_url == clean,
                    )
                )
            )
            or 0
        )
        if max_del:
            stale_rows = list(
                (
                    await session.scalars(
                        select(Subscription).where(
                            Subscription.user_id == user.id,
                            Subscription.podcast_url == clean,
                            Subscription.deleted == 0,
                            Subscription.created <= max_del,
                        )
                    )
                ).all()
            )
            for s in stale_rows:
                s.deleted = now_ts
            if stale_rows:
                await session.commit()
        try:
            for deviceid in target_devices:
                await subscription_service.apply_changes(
                    session, user, deviceid, [clean], []
                )
        except Exception as exc:  # noqa: BLE001
            return RedirectResponse(
                f"{prefix}/me/podcasts?error={exc!s}", status_code=303
            )
        return RedirectResponse(
            f"{prefix}/me/podcasts?notice=subscribed+on+{len(target_devices)}+device(s)",
            status_code=303,
        )

    @router.post("/me/podcasts/unsubscribe")
    async def me_unsubscribe(
        session: SessionDep,
        config: ConfigDep,
        user: UserDep,
        url: Annotated[str, Form()],
    ) -> Response:
        clean = (url or "").strip()
        prefix = config.dashboard_prefix
        if not clean:
            return RedirectResponse(
                f"{prefix}/me/podcasts?error=missing+url", status_code=303
            )
        # Mark subscriptions deleted across all of user's devices.
        from sqlalchemy import update as _update
        import time as _time

        await session.execute(
            _update(Subscription)
            .where(
                Subscription.user_id == user.id,
                Subscription.podcast_url == clean,
                Subscription.deleted == 0,
            )
            .values(deleted=int(_time.time()))
        )
        await session.commit()
        return RedirectResponse(
            f"{prefix}/me/podcasts?notice=unsubscribed", status_code=303
        )

    @router.get("/me/episodes", response_class=HTMLResponse)
    async def me_episodes(
        request: Request, session: SessionDep, config: ConfigDep, user: UserDep
    ) -> Response:
        favs = list(
            (
                await session.scalars(
                    select(Favorite)
                    .where(Favorite.user_id == user.id)
                    .order_by(Favorite.created.desc())
                )
            ).all()
        )
        recent_rows = list(
            (
                await session.execute(
                    select(
                        EpisodeAction.podcast_url,
                        EpisodeAction.episode_url,
                        func.max(EpisodeAction.uploaded).label("last_seen"),
                        func.count(EpisodeAction.id).label("action_count"),
                    )
                    .where(EpisodeAction.user_id == user.id)
                    .group_by(EpisodeAction.podcast_url, EpisodeAction.episode_url)
                    .order_by(func.max(EpisodeAction.uploaded).desc())
                    .limit(50)
                )
            ).all()
        )
        urls_needed = {r.podcast_url for r in recent_rows} | {f.podcast_url for f in favs}
        feeds = await feed_service.fetch_many(urls_needed)
        recent = []
        for r in recent_rows:
            feed = feeds.get(r.podcast_url)
            ep = feed_service.episode_for(feed, r.episode_url) if feed else None
            recent.append(
                {
                    "podcast_url": r.podcast_url,
                    "episode_url": r.episode_url,
                    "last_seen": int(r.last_seen or 0),
                    "action_count": int(r.action_count or 0),
                    "podcast_title": feed.title if feed else r.podcast_url,
                    "podcast_image": feed.image if feed else None,
                    "episode_title": ep.title if ep else None,
                    "pub_date": ep.pub_date if ep else None,
                    "duration": ep.duration if ep else None,
                }
            )
        favorites = []
        for f in favs:
            feed = feeds.get(f.podcast_url)
            ep = feed_service.episode_for(feed, f.episode_url) if feed else None
            favorites.append(
                {
                    "podcast_url": f.podcast_url,
                    "episode_url": f.episode_url,
                    "title": f.title or (ep.title if ep else None),
                    "podcast_title": feed.title if feed else f.podcast_url,
                    "podcast_image": feed.image if feed else None,
                    "pub_date": ep.pub_date if ep else None,
                    "duration": ep.duration if ep else None,
                }
            )
        admin_flag = await is_admin(config, session, user.username)
        return _TEMPLATES.TemplateResponse(
            request,
            "me_episodes.html",
            _ctx(
                request,
                config,
                user=user,
                is_admin=admin_flag,
                favorites=favorites,
                recent=recent,
            ),
        )

    @router.get("/me/actions", response_class=HTMLResponse)
    async def me_actions(
        request: Request,
        session: SessionDep,
        config: ConfigDep,
        user: UserDep,
        action: str | None = None,
        device: str | None = None,
        podcast: str | None = None,
        sort: str = "uploaded_desc",
        page: int = 1,
        per_page: int = 50,
    ) -> Response:
        per_page = max(10, min(int(per_page or 50), 200))
        page = max(1, int(page or 1))
        base_filters = [EpisodeAction.user_id == user.id]
        if action:
            base_filters.append(EpisodeAction.action == action)
        if device:
            base_filters.append(EpisodeAction.device_id == device)
        if podcast:
            base_filters.append(EpisodeAction.podcast_url == podcast)

        total = int(
            (
                await session.scalar(
                    select(func.count(EpisodeAction.id)).where(*base_filters)
                )
            )
            or 0
        )
        sort_map = {
            "uploaded_desc": EpisodeAction.uploaded.desc(),
            "uploaded_asc": EpisodeAction.uploaded.asc(),
            "action_asc": EpisodeAction.action.asc(),
            "action_desc": EpisodeAction.action.desc(),
            "podcast_asc": EpisodeAction.podcast_url.asc(),
            "podcast_desc": EpisodeAction.podcast_url.desc(),
        }
        order_clause = sort_map.get(sort, sort_map["uploaded_desc"])
        stmt = (
            select(EpisodeAction)
            .where(*base_filters)
            .order_by(order_clause)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        rows = list((await session.scalars(stmt)).all())
        total_pages = max(1, (total + per_page - 1) // per_page)
        podcast_urls = list(
            (
                await session.scalars(
                    select(EpisodeAction.podcast_url)
                    .where(EpisodeAction.user_id == user.id)
                    .distinct()
                )
            ).all()
        )
        action_types = list(
            (
                await session.scalars(
                    select(EpisodeAction.action)
                    .where(EpisodeAction.user_id == user.id)
                    .distinct()
                )
            ).all()
        )
        device_ids = list(
            (
                await session.scalars(
                    select(EpisodeAction.device_id)
                    .where(
                        EpisodeAction.user_id == user.id,
                        EpisodeAction.device_id.is_not(None),
                    )
                    .distinct()
                )
            ).all()
        )
        admin_flag = await is_admin(config, session, user.username)
        feed_url_set = {r.podcast_url for r in rows} | set(podcast_urls)
        feeds = await feed_service.fetch_many(feed_url_set)
        items = []
        for r in rows:
            feed = feeds.get(r.podcast_url)
            ep = feed_service.episode_for(feed, r.episode_url) if feed else None
            items.append(
                {
                    "row": r,
                    "podcast_title": feed.title if feed else r.podcast_url,
                    "podcast_image": feed.image if feed else None,
                    "episode_title": ep.title if ep else None,
                }
            )
        podcast_options = sorted(
            (
                {"url": u, "title": (feeds.get(u).title if feeds.get(u) else u)}
                for u in podcast_urls
            ),
            key=lambda p: p["title"].lower(),
        )
        return _TEMPLATES.TemplateResponse(
            request,
            "me_actions.html",
            _ctx(
                request,
                config,
                user=user,
                is_admin=admin_flag,
                items=items,
                action_types=sorted(action_types),
                device_ids=sorted(d for d in device_ids if d),
                podcast_options=podcast_options,
                filter_action=action or "",
                filter_device=device or "",
                filter_podcast=podcast or "",
                sort=sort,
                page=page,
                per_page=per_page,
                total=total,
                total_pages=total_pages,
            ),
        )

    @router.get("/me/devices", response_class=HTMLResponse)
    async def me_devices(
        request: Request, session: SessionDep, config: ConfigDep, user: UserDep
    ) -> Response:
        devices = list(
            (
                await session.scalars(
                    select(Device).where(Device.user_id == user.id).order_by(Device.id)
                )
            ).all()
        )
        sub_rows = (
            await session.execute(
                select(
                    Subscription.device_id,
                    func.count(func.distinct(Subscription.podcast_url)),
                )
                .where(Subscription.user_id == user.id, Subscription.deleted == 0)
                .group_by(Subscription.device_id)
            )
        ).all()
        sub_by_device = {int(d): int(c) for d, c in sub_rows}
        admin_flag = await is_admin(config, session, user.username)
        return _TEMPLATES.TemplateResponse(
            request,
            "me_devices.html",
            _ctx(
                request,
                config,
                user=user,
                is_admin=admin_flag,
                devices=devices,
                sub_by_device=sub_by_device,
            ),
        )

    @router.get("/me/stats", response_class=HTMLResponse)
    async def me_stats(
        request: Request, session: SessionDep, config: ConfigDep, user: UserDep
    ) -> Response:
        per_action_rows = (
            await session.execute(
                select(EpisodeAction.action, func.count(EpisodeAction.id))
                .where(EpisodeAction.user_id == user.id)
                .group_by(EpisodeAction.action)
                .order_by(func.count(EpisodeAction.id).desc())
            )
        ).all()
        per_action = [(a, int(c)) for a, c in per_action_rows]
        per_device_rows = (
            await session.execute(
                select(EpisodeAction.device_id, func.count(EpisodeAction.id))
                .where(EpisodeAction.user_id == user.id)
                .group_by(EpisodeAction.device_id)
                .order_by(func.count(EpisodeAction.id).desc())
            )
        ).all()
        per_device = [(d or "(none)", int(c)) for d, c in per_device_rows]
        top_podcasts_rows = (
            await session.execute(
                select(EpisodeAction.podcast_url, func.count(EpisodeAction.id))
                .where(EpisodeAction.user_id == user.id)
                .group_by(EpisodeAction.podcast_url)
                .order_by(func.count(EpisodeAction.id).desc())
                .limit(10)
            )
        ).all()
        top_urls = [p for p, _ in top_podcasts_rows]
        top_feeds = await feed_service.fetch_many(top_urls)
        top_podcasts = [
            {
                "url": p,
                "count": int(c),
                "title": (top_feeds.get(p).title if top_feeds.get(p) else p),
                "image": (top_feeds.get(p).image if top_feeds.get(p) else None),
            }
            for p, c in top_podcasts_rows
        ]
        per_episode_rows = (
            await session.execute(
                select(
                    EpisodeAction.podcast_url,
                    EpisodeAction.episode_url,
                    func.max(EpisodeAction.position).label("max_pos"),
                )
                .where(
                    EpisodeAction.user_id == user.id,
                    EpisodeAction.action == "play",
                    EpisodeAction.position.is_not(None),
                )
                .group_by(EpisodeAction.podcast_url, EpisodeAction.episode_url)
            )
        ).all()
        listened_seconds = sum(int(p or 0) for _, _, p in per_episode_rows)
        episodes_started = len(per_episode_rows)
        # Resolve completion from RSS duration (action.total unreliable)
        feed_map = await feed_service.fetch_many(
            {pu for pu, _, _ in per_episode_rows}
        )

        def _dur_secs(value: str | None) -> int:
            if not value:
                return 0
            v = value.strip()
            if not v:
                return 0
            if ":" in v:
                try:
                    parts = [int(p) for p in v.split(":")]
                except ValueError:
                    return 0
                total = 0
                for n in parts:
                    total = total * 60 + n
                return total
            try:
                return int(float(v))
            except ValueError:
                return 0

        episodes_completed = 0
        for podcast_url, episode_url, pos in per_episode_rows:
            feed = feed_map.get(podcast_url)
            if feed is None:
                continue
            ep = feed.episode_by_url.get(episode_url)
            if ep is None:
                continue
            dur = _dur_secs(ep.duration)
            if dur > 60 and pos and int(pos) >= dur - 15:
                episodes_completed += 1
        first_ts = int(
            (
                await session.scalar(
                    select(func.min(EpisodeAction.uploaded)).where(
                        EpisodeAction.user_id == user.id
                    )
                )
            )
            or 0
        )
        last_ts = int(
            (
                await session.scalar(
                    select(func.max(EpisodeAction.uploaded)).where(
                        EpisodeAction.user_id == user.id
                    )
                )
            )
            or 0
        )
        admin_flag = await is_admin(config, session, user.username)
        return _TEMPLATES.TemplateResponse(
            request,
            "me_stats.html",
            _ctx(
                request,
                config,
                user=user,
                is_admin=admin_flag,
                per_action=per_action,
                per_device=per_device,
                top_podcasts=top_podcasts,
                listened_seconds=listened_seconds,
                episodes_started=episodes_started,
                episodes_completed=episodes_completed,
                first_ts=first_ts,
                last_ts=last_ts,
            ),
        )

    @router.get("/me/podcast", response_class=HTMLResponse)
    async def me_podcast(
        request: Request,
        session: SessionDep,
        config: ConfigDep,
        user: UserDep,
        url: str,
    ) -> Response:
        # Account-level active check: latest creation across devices must be
        # newer than latest deletion (matches /me/podcasts logic).
        max_created_row = await session.scalar(
            select(func.coalesce(func.max(Subscription.created), 0)).where(
                Subscription.user_id == user.id,
                Subscription.podcast_url == url,
                Subscription.deleted == 0,
            )
        )
        max_deleted_row = await session.scalar(
            select(func.coalesce(func.max(Subscription.deleted), 0)).where(
                Subscription.user_id == user.id,
                Subscription.podcast_url == url,
            )
        )
        sub_active = int(max_created_row or 0) > int(max_deleted_row or 0)
        feed = await feed_service.fetch(url)
        action_rows = list(
            (
                await session.scalars(
                    select(EpisodeAction).where(
                        EpisodeAction.user_id == user.id,
                        EpisodeAction.podcast_url == url,
                    ).order_by(EpisodeAction.uploaded.desc())
                )
            ).all()
        )
        actions_by_episode: dict[str, list[EpisodeAction]] = {}
        for a in action_rows:
            actions_by_episode.setdefault(a.episode_url, []).append(a)

        def _parse_dur(value: str | None) -> int | None:
            if not value:
                return None
            v = value.strip()
            if not v:
                return None
            if ":" in v:
                parts = v.split(":")
                try:
                    nums = [int(p) for p in parts]
                except ValueError:
                    return None
                total = 0
                for n in nums:
                    total = total * 60 + n
                return total
            try:
                return int(float(v))
            except ValueError:
                return None

        episodes = []
        for ep in feed.episodes:
            acts = actions_by_episode.get(ep.url, [])
            plays = [a for a in acts if a.action == "play"]
            # action_rows is ordered by uploaded DESC, so plays[0] is most recent
            latest = plays[0] if plays else None
            latest_pos = int(latest.position) if latest and latest.position else 0
            # AntennaPod sends started=position=total for every action, so
            # action.total is unreliable. Use RSS <itunes:duration> only.
            duration_secs = _parse_dur(ep.duration) or 0
            completed = (
                duration_secs > 60
                and latest_pos > 0
                and latest_pos >= duration_secs - 15
            )
            resume_at = 0 if completed else latest_pos
            progress_pct = (
                round(latest_pos / duration_secs * 100, 1)
                if duration_secs and latest_pos
                else 0
            )
            if progress_pct > 100:
                progress_pct = 100
            episodes.append(
                {
                    "title": ep.title,
                    "url": ep.url,
                    "pub_date": ep.pub_date,
                    "pub_ts": ep.pub_ts,
                    "duration": ep.duration,
                    "duration_secs": duration_secs,
                    "description": ep.description,
                    "action_count": len(acts),
                    "play_count": len(plays),
                    "latest_position": latest_pos,
                    "completed": completed,
                    "resume_at": resume_at,
                    "progress_pct": progress_pct,
                }
            )

        admin_flag = await is_admin(config, session, user.username)
        return _TEMPLATES.TemplateResponse(
            request,
            "me_podcast.html",
            _ctx(
                request,
                config,
                user=user,
                is_admin=admin_flag,
                feed=feed,
                episodes=episodes,
                subscribed=bool(sub_active),
                action_count=len(action_rows),
            ),
        )

    @router.get("/me/discover", response_class=HTMLResponse)
    async def me_discover(
        request: Request,
        session: SessionDep,
        config: ConfigDep,
        user: UserDep,
        q: str = "",
        country: str = "US",
    ) -> Response:
        results = await discover_service.search(q, country=country) if q else []
        from sqlalchemy import case as _case_disc

        rows_sub = (
            await session.execute(
                select(
                    Subscription.podcast_url,
                    func.max(
                        _case_disc(
                            (Subscription.deleted == 0, Subscription.created), else_=0
                        )
                    ).label("mc"),
                    func.max(Subscription.deleted).label("md"),
                )
                .where(Subscription.user_id == user.id)
                .group_by(Subscription.podcast_url)
            )
        ).all()
        subscribed_urls = {
            row.podcast_url
            for row in rows_sub
            if int(row.mc or 0) > int(row.md or 0)
        }
        admin_flag = await is_admin(config, session, user.username)
        return _TEMPLATES.TemplateResponse(
            request,
            "me_discover.html",
            _ctx(
                request,
                config,
                user=user,
                is_admin=admin_flag,
                q=q,
                country=country,
                results=results,
                subscribed_urls=subscribed_urls,
            ),
        )

    @router.get("/me/debug", response_class=HTMLResponse)
    async def me_debug(
        request: Request,
        session: SessionDep,
        config: ConfigDep,
        user: UserDep,
        limit: int = 20,
    ) -> Response:
        import json
        import os
        from pathlib import Path as _PathL

        path_raw = os.environ.get("GPODDER_DEBUG_ACTIONS_FILE", "")
        entries: list[dict] = []
        path_exists = False
        path_str = path_raw or "(unset — set GPODDER_DEBUG_ACTIONS_FILE to enable)"
        if path_raw:
            p = _PathL(path_raw).expanduser()
            path_str = str(p)
            if p.is_file():
                path_exists = True
                limit = max(1, min(int(limit or 20), 200))
                try:
                    with p.open("r", encoding="utf-8", errors="replace") as fh:
                        lines = fh.readlines()
                    for line in lines[-limit:]:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            entries.append({"raw": line.rstrip()})
                    entries.reverse()
                except OSError as exc:
                    entries.append({"error": str(exc)})
        admin_flag = await is_admin(config, session, user.username)
        return _TEMPLATES.TemplateResponse(
            request,
            "me_debug.html",
            _ctx(
                request,
                config,
                user=user,
                is_admin=admin_flag,
                entries=entries,
                path=path_str,
                path_exists=path_exists,
                limit=limit,
            ),
        )

    return router
