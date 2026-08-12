class ProviderRateLimitedError(Exception):
    """Common base for every article-source client's 429 signal (arXiv, OpenAlex,
    Semantic Scholar, ...). External APIs' 429s here mean quota/pool exhaustion,
    not a transient blip — orchestration layers (e.g. ScrapeExecutor) catch this
    base type, not each provider's subclass individually, so a new client gets
    the same "abort remaining same-host work this run" treatment for free."""
