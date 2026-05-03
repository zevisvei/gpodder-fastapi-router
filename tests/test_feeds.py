from __future__ import annotations

from gpodder_router.services import feeds as feed_service

SAMPLE_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Sample Podcast</title>
    <description>A &lt;b&gt;great&lt;/b&gt; show.</description>
    <link>https://example.org/sample</link>
    <itunes:author>Jane Host</itunes:author>
    <itunes:image href="https://example.org/cover.jpg"/>
    <item>
      <title>Episode One</title>
      <description>Pilot episode</description>
      <enclosure url="https://example.org/ep1.mp3" length="100" type="audio/mpeg"/>
      <pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
      <itunes:duration>1800</itunes:duration>
      <guid>ep1-guid</guid>
    </item>
    <item>
      <title>Episode Two</title>
      <enclosure url="https://example.org/ep2.mp3" length="200" type="audio/mpeg"/>
      <itunes:duration>45:00</itunes:duration>
    </item>
  </channel>
</rss>
"""


def test_parse_feed_extracts_metadata() -> None:
    feed = feed_service._parse_feed("https://example.org/feed", SAMPLE_RSS)
    assert feed.title == "Sample Podcast"
    assert feed.author == "Jane Host"
    assert feed.image == "https://example.org/cover.jpg"
    assert feed.link == "https://example.org/sample"
    assert "great" in (feed.description or "")
    assert "<b>" not in (feed.description or "")
    assert len(feed.episodes) == 2

    ep1 = feed.episode_by_url["https://example.org/ep1.mp3"]
    assert ep1.title == "Episode One"
    assert ep1.duration == "1800"
    assert ep1.pub_ts and ep1.pub_ts > 0
    assert feed.episode_by_url["ep1-guid"] is ep1

    ep2 = feed.episode_by_url["https://example.org/ep2.mp3"]
    assert ep2.title == "Episode Two"
    assert ep2.duration == "45:00"


def test_safe_url_rejects_non_http() -> None:
    assert feed_service._safe_url("https://x.example/feed")
    assert feed_service._safe_url("http://x.example/feed")
    assert not feed_service._safe_url("file:///etc/passwd")
    assert not feed_service._safe_url("ftp://x.example/feed")
    assert not feed_service._safe_url("not-a-url")
