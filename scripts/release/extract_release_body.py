#!/usr/bin/env python3
"""
Extract the release body for a given tag from release-notes.json.
Writes a GitHub Actions multiline output variable named 'body'.

Usage (in GitHub Actions):
    python3 scripts/release/extract_release_body.py <tag>
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
RELEASE_NOTES_PATH = ROOT / 'frontend' / 'public' / 'release-notes.json'


def main() -> None:
    if len(sys.argv) < 2:
        print('[error] usage: extract_release_body.py <tag>', file=sys.stderr)
        sys.exit(1)

    tag = sys.argv[1]

    with open(RELEASE_NOTES_PATH) as f:
        entries = json.load(f)

    entry = next((e for e in entries if e.get('version') == tag), None)

    if not entry or not entry.get('changes'):
        body = '_No release notes._'
    else:
        lines = [f"- **{c['type']}**: {c['description']}" for c in entry['changes']]
        body = '\n'.join(lines)

    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as out:
            out.write('body<<EOF_NOTES\n')
            out.write(body + '\n')
            out.write('EOF_NOTES\n')
    else:
        print(body)


if __name__ == '__main__':
    main()
