from __future__ import annotations

from enum import Enum


class Format(str, Enum):
    json = "json"
    xml = "xml"
    opml = "opml"
    txt = "txt"
    jsonp = "jsonp"


class SettingsScope(str, Enum):
    account = "account"
    device = "device"
    podcast = "podcast"
    episode = "episode"
