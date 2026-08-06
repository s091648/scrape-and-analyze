import responses


@responses.activate
def test_fetch_feed_captures_content_encoded():
    """WordPress-style feeds embed the full article body in <content:encoded> —
    RssClient must surface it on RssEntry.content rather than discarding it."""
    from src.infrastructure.collection.clients.rss_client import RssClient

    rss = '''<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
    <channel>
      <item>
        <title>Full Content Article</title>
        <link>https://example.com/full-article</link>
        <description>Short excerpt.</description>
        <content:encoded><![CDATA[<p>The full article body, much longer than the excerpt.</p>]]></content:encoded>
      </item>
    </channel></rss>'''
    responses.add(responses.GET, "https://example.com/feed", body=rss, status=200)

    entries = RssClient().fetch_feed("https://example.com/feed")

    assert len(entries) == 1
    assert "full article body" in entries[0].content


@responses.activate
def test_fetch_feed_content_is_none_when_absent():
    """Feeds without <content:encoded> must not error — content stays None."""
    from src.infrastructure.collection.clients.rss_client import RssClient

    rss = '''<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>No Content Encoded</title>
        <link>https://example.com/plain-article</link>
        <description>Just a description.</description>
      </item>
    </channel></rss>'''
    responses.add(responses.GET, "https://example.com/feed", body=rss, status=200)

    entries = RssClient().fetch_feed("https://example.com/feed")

    assert len(entries) == 1
    assert entries[0].content is None
