# Client compatibility

The router implements mygpo API 2.11. Anything that talks to gpodder.net
should work; tested against:

| Client       | Auth flow                | Notes                                  |
|--------------|--------------------------|----------------------------------------|
| AntennaPod   | Basic on login, then `sessionid` cookie | Server URL is the host you run on (e.g. `https://your.host`); leave path empty. Sync via "Settings → Synchronization → gpodder.net". |
| gPodder (desktop) | Basic on every request | Set hostname / username / password under Preferences → gpodder.net. |
| Podverse     | Basic                    | Configure `Custom server` in app settings. |
| Kasts        | Basic                    | Same.                                  |
| Podgrab / clones | Basic                | Pass `--gpodder-url` if the client supports it. |

## Endpoints clients hit

Most clients only use:

- `POST /api/2/auth/{u}/login.json`
- `GET  /api/2/devices/{u}.json` — to discover device IDs
- `POST /api/2/devices/{u}/{d}.json` — register the local device
- `GET  /api/2/subscriptions/{u}/{d}.json?since=...` — pull deltas
- `POST /api/2/subscriptions/{u}/{d}.json` — push deltas
- `GET  /api/2/episodes/{u}.json?since=...` — pull episode actions
- `POST /api/2/episodes/{u}.json` — push episode actions

The directory / suggestions / favorites endpoints are stubbed in this
router (return empty results); clients that don't display server
suggestions are unaffected.

## Reverse-proxy caveats

If the client refuses to log in, check:

1. Server time: bcrypt is fine but session cookies have absolute
   expiry; very wrong system clocks can invalidate them.
2. `Set-Cookie` not stripped by the proxy — confirm with `curl -i`.
3. HTTPS vs HTTP — some clients require HTTPS for Basic auth.
4. `Authorization` header forwarded by the proxy.
