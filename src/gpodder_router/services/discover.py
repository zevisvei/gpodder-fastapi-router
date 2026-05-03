from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from urllib import request
from urllib.parse import urlencode

ITUNES_SEARCH = "https://itunes.apple.com/search"
DEFAULT_TTL = 5 * 60  # 5 min

_CACHE: dict[str, tuple[int, list["DiscoverResult"]]] = {}
_LOCK = asyncio.Lock()


@dataclass
class DiscoverResult:
    feed_url: str
    title: str
    author: str | None = None
    image: str | None = None
    genre: str | None = None
    track_count: int | None = None
    country: str | None = None
    extra: dict = field(default_factory=dict)


def _http_get_json(url: str, timeout: float = 8.0) -> dict:
    req = request.Request(
        url,
        headers={
            "User-Agent": "gpodder-fastapi-router/0.1 (+podcast discover)",
            "Accept": "application/json",
        },
    )
    with request.urlopen(req, timeout=timeout) as resp:
        body = resp.read(4 * 1024 * 1024)
    return json.loads(body.decode("utf-8"))


def _parse(data: dict) -> list[DiscoverResult]:
    out: list[DiscoverResult] = []
    for r in data.get("results", []) or []:
        feed = (r.get("feedUrl") or "").strip()
        if not feed:
            continue
        out.append(
            DiscoverResult(
                feed_url=feed,
                title=(r.get("collectionName") or r.get("trackName") or feed).strip(),
                author=(r.get("artistName") or "").strip() or None,
                image=(
                    r.get("artworkUrl600")
                    or r.get("artworkUrl100")
                    or r.get("artworkUrl60")
                    or None
                ),
                genre=(r.get("primaryGenreName") or "").strip() or None,
                track_count=r.get("trackCount"),
                country=(r.get("country") or "").strip() or None,
            )
        )
    return out


async def search(
    term: str, *, country: str = "US", limit: int = 30, ttl: int = DEFAULT_TTL
) -> list[DiscoverResult]:
    term = (term or "").strip()
    if not term:
        return []
    limit = max(1, min(int(limit or 30), 100))
    key = f"{country}|{limit}|{term.lower()}"
    now = int(time.time())
    cached = _CACHE.get(key)
    if cached and cached[0] + ttl > now:
        return cached[1]
    async with _LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] + ttl > now:
            return cached[1]
        params = {
            "term": term,
            "media": "podcast",
            "entity": "podcast",
            "limit": str(limit),
            "country": country,
        }
        url = f"{ITUNES_SEARCH}?{urlencode(params)}"
        try:
            data = await asyncio.to_thread(_http_get_json, url)
            results = _parse(data)
        except Exception:  # noqa: BLE001
            results = []
        _CACHE[(key)] = (now, results)
        return results


def clear_cache() -> None:
    _CACHE.clear()
