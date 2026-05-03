from __future__ import annotations

import urllib.parse

_PREFIXES = {
    "fb:": "http://feeds.feedburner.com/%s",
    "yt:": "http://www.youtube.com/rss/user/%s/videos.rss",
    "sc:": "http://soundcloud.com/%s",
    "fm4od:": "http://onapp1.orf.at/webcam/fm4/fod/%s.xspf",
    "ytpl:": "http://gdata.youtube.com/feeds/api/playlists/%s",
}

_ALLOWED_SCHEMES = ("http", "https", "ftp", "file")
_FEED_ALIAS = ("feed", "itpc", "itms")


def normalize_feed_url(url: str | None) -> str | None:
    """Port of mygpo.utils.normalize_feed_url.

    - Lowercases scheme and host.
    - Strips HTTP authentication (everything before the last "@" in netloc).
    - URL-encodes path with safe="/%" and query with safe=":&=" (quote_plus).
    - Empty path becomes "/".
    - feed:// / itpc:// / itms:// rewritten to http://.
    - Schemes not in {http, https, ftp, file} return None.
    - Prefixes (fb:, yt:, sc:, fm4od:, ytpl:) are expanded.
    - Returns None for empty input or input shorter than 8 characters.
    """
    if url is None:
        return None
    url = url.strip()
    if not url or len(url) < 8:
        return None

    for prefix, expansion in _PREFIXES.items():
        if url.startswith(prefix):
            url = expansion % (url[len(prefix):],)
            break

    if "://" not in url:
        url = "http://" + url

    scheme, netloc, path, query, fragment = urllib.parse.urlsplit(url)
    scheme, netloc = scheme.lower(), netloc.lower()
    path = urllib.parse.quote(path, "/%")
    query = urllib.parse.quote_plus(query, ":&=")
    netloc = netloc.rsplit("@", 1)[-1]

    if path == "":
        path = "/"
    if scheme in _FEED_ALIAS:
        scheme = "http"
    if scheme not in _ALLOWED_SCHEMES:
        return None

    return urllib.parse.urlunsplit((scheme, netloc, path, query, fragment))
