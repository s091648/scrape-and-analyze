#!/usr/bin/env python3
"""
Generate LLM-summarized release notes from git commits since the last tag.
Updates the {{NEWEST_VERSION}} entry's changes in frontend/public/release-notes.json.

The script loads LLM provider config from the staging DB (via DATABASE_URL or
STAGING_DB_URL), then uses ResilientLLMService to summarize recent commits into
a structured changes array.

Usage:
    DATABASE_URL=postgresql://... uv run python scripts/release/generate_release_notes.py
    DATABASE_URL=postgresql://... uv run python scripts/release/generate_release_notes.py --dry-run

Required env vars:
    DATABASE_URL or STAGING_DB_URL  — staging DB connection string
    LLM API keys matching the api_key_env column of each active provider
    (e.g. GEMINI_API_KEY, CLAUDE_API_KEY, OPENROUTER_API_KEY)
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
RELEASE_NOTES_PATH = ROOT / 'frontend' / 'public' / 'release-notes.json'

sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _get_prev_tag() -> str | None:
    try:
        out = subprocess.check_output(
            ['git', 'tag', '--sort=-version:refname'],
            cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
        tags = [t for t in out.split('\n') if t]
        return tags[0] if tags else None
    except subprocess.CalledProcessError:
        return None


def get_commits_since_last_tag() -> str:
    prev = _get_prev_tag()
    if prev:
        cmd = ['git', 'log', f'{prev}..HEAD', '--oneline', '--no-merges']
    else:
        cmd = ['git', 'log', '--oneline', '--no-merges', '-100']
    try:
        return subprocess.check_output(cmd, cwd=ROOT, text=True).strip()
    except subprocess.CalledProcessError as e:
        print(f'[error] git log failed: {e}', file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# LLM service assembly (mirrors bootstrap.build_llm_service)
# ---------------------------------------------------------------------------

def build_llm_service(session):
    from shared.llm_provider import load_active_providers
    from src.infrastructure.intelligence.llm.resilient_llm_service import ResilientLLMService, ProviderHandler
    from src.infrastructure.intelligence.llm.providers import ClaudeProvider, GeminiProvider, OpenRouterProvider
    from src.infrastructure.intelligence.llm.rate_limit import SlidingWindowStrategy, NoOpStrategy

    def _make_strategy(cfg):
        s = cfg.get('strategy', {})
        if s.get('type') == 'sliding_window':
            return SlidingWindowStrategy(rpm=s['rpm'], tpm=s['tpm'], rpd=s['rpd'])
        return NoOpStrategy()

    handlers = []
    for cfg in load_active_providers(session):
        name = cfg['name']
        api_key = os.environ.get(cfg['api_key_env'], '')
        if not api_key:
            print(f'[warn] skipping {name}: env var {cfg["api_key_env"]} not set')
            continue
        if name == 'claude':
            provider = ClaudeProvider(api_key=api_key, model=cfg['model'])
        elif name == 'gemini':
            provider = GeminiProvider(api_key=api_key, model=cfg['model'])
        elif name == 'openrouter':
            provider = OpenRouterProvider(api_key=api_key, model=cfg['model'])
        else:
            print(f'[warn] unknown provider type: {name}')
            continue
        handlers.append(ProviderHandler(
            provider=provider,
            strategy=_make_strategy(cfg),
            priority=cfg['priority'],
            name=name,
        ))
        print(f'[info] loaded provider: {name} ({cfg["model"]})')

    if not handlers:
        raise ValueError('No active LLM providers with API keys available')

    return ResilientLLMService(handlers)


# ---------------------------------------------------------------------------
# LLM prompt & generation
# ---------------------------------------------------------------------------

_PROMPT = """\
You are a technical writer generating release notes for a web application.

Given the following git commit messages, produce a concise list of 3-8 user-facing changes.

Rules:
- Only include features, bug fixes, and notable improvements
- Skip CI, tests, chores, dependency bumps, and refactors unless user-facing
- Each description must be one sentence, written for end users (not developers)
- Categorize each as exactly one of: "feat", "fix", or "chore"
- Return ONLY a valid JSON array with no markdown fences, no prose, no explanation

Output format (example):
[
  {{"type": "feat", "description": "Added export to CSV for article lists"}},
  {{"type": "fix", "description": "Fixed pagination resetting when filters are applied"}}
]

Commits to summarize:
{commits}
"""


def generate_changes(llm_service, commits: str) -> list[dict]:
    prompt = _PROMPT.format(commits=commits)
    raw = llm_service.translate(commits, prompt)
    if raw is None:
        raise RuntimeError('All LLM providers exhausted — could not generate changes')

    raw = raw.strip()
    if raw.startswith('```'):
        lines = raw.split('\n')
        raw = '\n'.join(lines[1:-1]).strip()

    changes = json.loads(raw)
    if not isinstance(changes, list):
        raise ValueError(f'Expected JSON array, got: {type(changes)}')
    for item in changes:
        if 'type' not in item or 'description' not in item:
            raise ValueError(f'Malformed change entry: {item}')

    return changes


# ---------------------------------------------------------------------------
# File update
# ---------------------------------------------------------------------------

def update_release_notes(changes: list[dict]) -> None:
    with open(RELEASE_NOTES_PATH) as f:
        entries = json.load(f)

    placeholder_idx = next(
        (i for i, e in enumerate(entries) if '{{' in e.get('version', '')),
        None,
    )

    if placeholder_idx is not None:
        entries[placeholder_idx]['changes'] = changes
    else:
        entries.insert(0, {
            'version': '{{NEWEST_VERSION}}',
            'date': '{{RELEASE_DATE}}',
            'changes': changes,
        })

    with open(RELEASE_NOTES_PATH, 'w') as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
        f.write('\n')

    print(f'[ok] Wrote {len(changes)} change(s) to {RELEASE_NOTES_PATH}')


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='Print generated changes without updating the file')
    args = parser.parse_args()

    database_url = os.environ.get('DATABASE_URL') or os.environ.get('STAGING_DB_URL')
    if not database_url:
        print('[error] Set DATABASE_URL or STAGING_DB_URL to the staging DB', file=sys.stderr)
        sys.exit(1)

    commits = get_commits_since_last_tag()
    if not commits:
        print('[warn] No commits found since last tag — nothing to generate')
        return
    print(f'[info] Found {len(commits.splitlines())} commit(s) to summarize')

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        llm_service = build_llm_service(session)
        changes = generate_changes(llm_service, commits)
    finally:
        session.close()
        engine.dispose()

    print(f'[info] Generated {len(changes)} change(s):')
    for c in changes:
        print(f'  [{c["type"]}] {c["description"]}')

    if args.dry_run:
        print('\n[dry-run] No file written.')
        return

    update_release_notes(changes)


if __name__ == '__main__':
    main()
