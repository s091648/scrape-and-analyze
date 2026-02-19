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
            'article_link': '.post-card a.post-card__link',
            'title': 'h1.post-title',
            'content': '.post-content',
        },
    },
    {
        'base_url': 'https://blogs.sw.siemens.com/digital-transformation',
        'source': 'siemens',
        'selectors': {
            'article_link': 'article.post a.entry-title-link',
            'title': 'h1.entry-title',
            'content': '.entry-content',
        },
    },
    {
        'base_url': 'https://aws.amazon.com/blogs/iot',
        'source': 'aws_iot',
        'selectors': {
            'article_link': '.blog-post a.title',
            'title': 'h1.blog-post-title',
            'content': '.blog-post-content',
        },
    },
    {
        'base_url': 'https://azure.microsoft.com/en-us/blog/topics/internet-of-things',
        'source': 'azure_iot',
        'selectors': {
            'article_link': '.card a.card-link',
            'title': 'h1.article-title',
            'content': '.article-content',
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


def validate_config() -> None:
    """Validate required configuration at startup"""
    errors = []

    db_url = os.environ.get('DATABASE_URL', DATABASE_URL)
    api_key = os.environ.get('LLM_API_KEY', LLM_API_KEY)

    if not db_url:
        errors.append("DATABASE_URL is required")

    if not api_key:
        errors.append("LLM_API_KEY is required")

    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
