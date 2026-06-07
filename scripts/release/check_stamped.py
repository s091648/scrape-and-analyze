#!/usr/bin/env python3
"""Exit 0 if the given tag version already exists in release-notes.json, else exit 1."""
import json
import sys
from pathlib import Path

RELEASE_NOTES_PATH = Path(__file__).parent.parent.parent / "frontend" / "public" / "release-notes.json"


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <tag>", file=sys.stderr)
        sys.exit(2)

    tag = sys.argv[1]
    entries = json.loads(RELEASE_NOTES_PATH.read_text())
    if any(e.get("version") == tag for e in entries):
        print(f"Version {tag} already stamped.")
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
