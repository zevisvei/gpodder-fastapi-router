# Admin dashboard

Mounted at `/dashboard` (configurable via `GPodderConfig.dashboard_prefix`)
when `enable_dashboard=True` (default). Disable by setting it to `False`.

## Pages

| Path                              | Description                            |
|-----------------------------------|----------------------------------------|
| `GET /dashboard/login`            | Login form                             |
| `POST /dashboard/login`           | Authenticate (form fields `username`, `password`) |
| `GET /dashboard/logout`           | Revoke session, redirect to login      |
| `GET /dashboard/`                 | Overview: counts of users, devices, subs, actions, lists |
| `GET /dashboard/users`            | List users + create form               |
| `POST /dashboard/users`           | Create user (`username`, `password`, optional `email`) |
| `POST /dashboard/users/{u}/delete`| Delete a user (and all related data)   |
| `POST /dashboard/users/{u}/password` | Reset password (`password` form field) |
| `GET /dashboard/users/{u}`        | Per-user detail: devices, subscriptions, action count |

The dashboard reuses the same `sessionid` cookie the API uses, so once
you log in via the dashboard form you can also call protected API
endpoints from the same browser without sending Basic auth.

## Admin authorisation

A user may sign in to the dashboard if **either**:

- their username appears in `GPodderConfig.admin_usernames`, or
- the list is empty and they are the **first** user by id (bootstrap).

Once `admin_usernames` is set, the bootstrap fallback no longer applies
— production deployments should set the list explicitly:

```python
GPodderConfig(admin_usernames=["alice", "ops"])
```

or via env:

```bash
export GPODDER_ADMIN_USERNAMES='["alice","ops"]'
```

## Theming

The dashboard ships with PicoCSS via CDN and a tiny custom file at
`/dashboard/static/dashboard.css`. Override by serving a file with the
same path from a higher-priority route, or fork the package.

## Disabling

```python
GPodderConfig(enable_dashboard=False)
```

or remove the include if you wire `build_router()` manually — the
dashboard is a separate router, not part of the API router.
