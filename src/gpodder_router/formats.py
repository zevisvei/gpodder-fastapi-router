from __future__ import annotations

import json
import string
import time
from collections.abc import Iterable
from typing import Any
from xml.sax.saxutils import escape

from fastapi import Response

from gpodder_router.exceptions import BadRequestError, InvalidFormatError
from gpodder_router.schemas.common import Format

_JSONP_ALLOWED = set(string.ascii_letters + string.digits + "_")


def _validate_jsonp(callback: str | None) -> str:
    """Mirror mygpo's JSONP padding check: only [A-Za-z0-9_]."""
    if not callback:
        raise BadRequestError(
            "For a JSONP response, specify the name of the callback function "
            "in the jsonp parameter"
        )
    if any(ch not in _JSONP_ALLOWED for ch in callback):
        raise BadRequestError(
            "JSONP padding can only contain letters, digits, and underscores"
        )
    return callback


def _opml(podcast_urls: Iterable[str], *, title: str = "gpodder subscriptions") -> str:
    body = "\n".join(
        f'    <outline type="rss" text="{escape(u)}" xmlUrl="{escape(u)}" />'
        for u in podcast_urls
    )
    now = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<opml version="2.0">\n'
        f"  <head><title>{escape(title)}</title>"
        f"<dateCreated>{now}</dateCreated></head>\n"
        f"  <body>\n{body}\n  </body>\n"
        "</opml>\n"
    )


def _xml(podcast_urls: Iterable[str]) -> str:
    items = "\n".join(f"  <podcast><url>{escape(u)}</url></podcast>" for u in podcast_urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<podcasts>\n{items}\n</podcasts>\n'


def _txt(podcast_urls: Iterable[str]) -> str:
    return "\n".join(podcast_urls) + ("\n" if podcast_urls else "")


def render_subscription_list(
    fmt: Format,
    podcast_urls: list[str],
    *,
    jsonp: str | None = None,
    title: str = "gpodder subscriptions",
) -> Response:
    if fmt is Format.json:
        return Response(json.dumps(podcast_urls), media_type="application/json")
    if fmt is Format.txt:
        return Response(_txt(podcast_urls), media_type="text/plain")
    if fmt is Format.opml:
        return Response(_opml(podcast_urls, title=title), media_type="text/x-opml+xml")
    if fmt is Format.xml:
        return Response(_xml(podcast_urls), media_type="application/xml")
    if fmt is Format.jsonp:
        cb = _validate_jsonp(jsonp)
        return Response(
            f"{cb}({json.dumps(podcast_urls)});",
            media_type="application/javascript",
        )
    raise InvalidFormatError(fmt.value)


def parse_subscription_payload(content_type: str, body: bytes, fmt: Format) -> list[str]:
    """Parse uploaded subscription bodies in the requested format."""
    text = body.decode("utf-8", errors="replace")
    if fmt is Format.json or content_type.startswith("application/json"):
        data = json.loads(text or "[]")
        if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
            raise InvalidFormatError("expected JSON array of URLs")
        return data
    if fmt is Format.txt:
        return [line.strip() for line in text.splitlines() if line.strip()]
    if fmt is Format.opml:
        # very small extractor, sufficient for round-tripping our own output
        import re

        return re.findall(r'xmlUrl="([^"]+)"', text)
    raise InvalidFormatError(fmt.value)


def render_generic(fmt: Format, payload: Any, *, jsonp: str | None = None) -> Response:
    """Render arbitrary JSON-serialisable payloads in the requested format."""
    if fmt is Format.json:
        return Response(json.dumps(payload), media_type="application/json")
    if fmt is Format.jsonp:
        cb = _validate_jsonp(jsonp)
        return Response(f"{cb}({json.dumps(payload)});", media_type="application/javascript")
    if fmt is Format.txt:
        if isinstance(payload, list):
            return Response(
                "\n".join(json.dumps(p) if not isinstance(p, str) else p for p in payload),
                media_type="text/plain",
            )
        return Response(json.dumps(payload), media_type="text/plain")
    if fmt is Format.xml:
        return Response(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<data>{escape(json.dumps(payload))}</data>',
            media_type="application/xml",
        )
    if fmt is Format.opml:
        if isinstance(payload, list) and all(isinstance(p, str) for p in payload):
            return Response(_opml(payload), media_type="text/x-opml+xml")
        raise InvalidFormatError("opml only valid for url lists")
    raise InvalidFormatError(fmt.value)
