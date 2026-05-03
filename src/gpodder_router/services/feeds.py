from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from html import unescape
from re import sub as _re_sub
from urllib import request
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
DEFAULT_TTL = 60 * 60  # 1 hour

_CACHE: dict[str, "PodcastFeed"] = {}
_LOCKS: dict[str, asyncio.Lock] = {}


@dataclass
class FeedEpisode:
    title: str
    url: str
    guid: str | None = None
    pub_date: str | None = None
    pub_ts: int | None = None
    duration: str | None = None
    description: str | None = None


@dataclass
class PodcastFeed:
    url: str
    title: str
    description: str | None = None
    image: str | None = None
    link: str | None = None
    author: str | None = None
    episodes: list[FeedEpisode] = field(default_factory=list)
    episode_by_url: dict[str, FeedEpisode] = field(default_factory=dict)
    fetched_at: int = 0
    error: str | None = None


def _strip_html(text: str | None) -> str | None:
    if not text:
        return None
    text = _re_sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = _re_sub(r"\s+", " ", text).strip()
    return text or None


def _parse_pub_ts(pub: str | None) -> int | None:
    if not pub:
        return None
    try:
        return int(parsedate_to_datetime(pub).timestamp())
    except (TypeError, ValueError):
        return None


def _parse_feed(url: str, body: bytes) -> PodcastFeed:
    root = ET.fromstring(body)
    channel = root.find("channel") if root.tag.lower().endswith("rss") else root
    if channel is None:
        channel = root

    title = (channel.findtext("title") or "").strip() or url
    description = _strip_html(channel.findtext("description"))
    link = (channel.findtext("link") or "").strip() or None
    author = (
        channel.findtext(f"{ITUNES}author")
        or channel.findtext("managingEditor")
        or ""
    ).strip() or None

    image: str | None = None
    img_el = channel.find("image/url")
    if img_el is not None and img_el.text:
        image = img_el.text.strip()
    if not image:
        itunes_img = channel.find(f"{ITUNES}image")
        if itunes_img is not None:
            image = itunes_img.get("href")

    episodes: list[FeedEpisode] = []
    by_url: dict[str, FeedEpisode] = {}
    for item in channel.findall("item"):
        ep_title = (item.findtext("title") or "").strip()
        enc = item.find("enclosure")
        ep_url = ""
        if enc is not None:
            ep_url = (enc.get("url") or "").strip()
        if not ep_url:
            ep_url = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "").strip() or None
        pub = (item.findtext("pubDate") or "").strip() or None
        dur = (item.findtext(f"{ITUNES}duration") or "").strip() or None
        ep_desc = _strip_html(
            item.findtext(f"{ITUNES}summary") or item.findtext("description")
        )
        ep = FeedEpisode(
            title=ep_title or ep_url or "(untitled)",
            url=ep_url,
            guid=guid,
            pub_date=pub,
            pub_ts=_parse_pub_ts(pub),
            duration=dur,
            description=ep_desc,
        )
        episodes.append(ep)
        if ep_url:
            by_url[ep_url] = ep
        if guid:
            by_url[guid] = ep

    return PodcastFeed(
        url=url,
        title=title,
        description=description,
        image=image,
        link=link,
        author=author,
        episodes=episodes,
        episode_by_url=by_url,
        fetched_at=int(time.time()),
    )


def _http_get(url: str, timeout: float = 8.0) -> bytes:
    req = request.Request(
        url,
        headers={
            "User-Agent": "gpodder-fastapi-router/0.1 (+podcast dashboard)",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    )
    with request.urlopen(req, timeout=timeout) as resp:
        data = resp.read(8 * 1024 * 1024)  # cap 8MB
    return data


def _safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


async def fetch(url: str, *, ttl: int = DEFAULT_TTL) -> PodcastFeed:
    now = int(time.time())
    cached = _CACHE.get(url)
    if cached and cached.fetched_at + ttl > now and not cached.error:
        return cached
    if not _safe_url(url):
        feed = PodcastFeed(
            url=url, title=url, fetched_at=now, error="invalid url"
        )
        _CACHE[url] = feed
        return feed

    lock = _LOCKS.setdefault(url, asyncio.Lock())
    async with lock:
        cached = _CACHE.get(url)
        if cached and cached.fetched_at + ttl > now and not cached.error:
            return cached
        try:
            body = await asyncio.to_thread(_http_get, url)
            feed = _parse_feed(url, body)
        except Exception as exc:  # noqa: BLE001
            feed = PodcastFeed(
                url=url, title=url, fetched_at=now, error=str(exc)[:200]
            )
        _CACHE[url] = feed
        return feed


async def fetch_many(urls) -> dict[str, PodcastFeed]:
    uniq = list(dict.fromkeys(urls))
    if not uniq:
        return {}
    results = await asyncio.gather(*[fetch(u) for u in uniq])
    return {f.url: f for f in results}


def episode_for(feed: PodcastFeed, episode_url: str) -> FeedEpisode | None:
    if not feed or not episode_url:
        return None
    return feed.episode_by_url.get(episode_url)


def clear_cache() -> None:
    _CACHE.clear()
    _LOCKS.clear()
