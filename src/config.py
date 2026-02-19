import os
from typing import List, Dict, Any

# Environment variables
DATABASE_URL = os.environ.get('DATABASE_URL', '')
LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'claude')
LLM_MODEL = os.environ.get('LLM_MODEL', 'claude-sonnet-4-20250514')
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')

# RSS Sources (daily)
RSS_SOURCES: List[Dict[str, Any]] = [
    {
        'url': 'https://techcrunch.com/feed/',
        'source': 'techcrunch',
    },
    {
        'url': 'https://venturebeat.com/feed/',
        'source': 'venturebeat',
    },
    {
        'url': 'https://www.iotworldtoday.com/rss.xml',
        'source': 'iotworldtoday',
    },
]

# Blog Sources (weekly)
BLOG_SOURCES: List[Dict[str, Any]] = [
    {
        'base_url': 'https://developer.nvidia.com/blog',
        'source': 'nvidia',
        'selectors': {
            'article_link': 'article a',
            'title': 'h1',
            'content': 'article .content',
        },
    },
    {
        'base_url': 'https://blogs.sw.siemens.com/digital-transformation',
        'source': 'siemens',
        'selectors': {
            'article_link': '.post-title a',
            'title': 'h1.entry-title',
            'content': '.entry-content',
        },
    },
]


def get_sources(schedule_type: str) -> List[Dict[str, Any]]:
    """Get sources based on schedule type"""
    if schedule_type == 'daily':
        return RSS_SOURCES
    elif schedule_type == 'weekly':
        return BLOG_SOURCES
    else:
        return []
