"""Wraps one terraform-docs markdown output into nested collapsible <details>
blocks for site/guide/architecture/terraform-services.md's "Terraform Modules"
section.

terraform-docs' own output uses the same heading level (`## `) for every
section (Requirements/Providers/Resources/Inputs/Outputs) regardless of
module — once several modules are concatenated on one page that reads as
flat/undifferentiated, with no visual distinction between "this is a module"
and "this is one of its sections". This turns those headings into actual
structure instead: one outer <details> per module (collapsed by default)
containing one <details open> per section (expanded by default, so a
section's table is visible as soon as its module is opened).

CommonMark's HTML block rules include `details`/`summary` as block-level tags
that end at the next blank line, so markdown (tables included) inside them is
still parsed as markdown as long as a blank line separates the opening
`<summary>` from the content and another separates the content from the
closing `</details>` — both preserved here.

Usage:
    <terraform-docs markdown output> | python scripts/wrap_terraform_module_doc.py <module-display-name>
"""
import re
import sys

SECTION_RE = re.compile(r"^## (.+)$", re.MULTILINE)


def wrap(raw_markdown, module_name):
    matches = list(SECTION_RE.finditer(raw_markdown))
    if not matches:
        # No `## ` sections found (unexpected, but don't silently drop content) —
        # fall back to one section holding everything as-is.
        sections = [("Content", raw_markdown.strip())]
    else:
        sections = []
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_markdown)
            sections.append((m.group(1).strip(), raw_markdown[start:end].strip()))

    parts = ['<details class="tf-module">', f"<summary>{module_name}</summary>", ""]
    for name, body in sections:
        parts.append('<details class="tf-module-section" open>')
        parts.append(f"<summary>{name}</summary>")
        parts.append("")
        parts.append(body)
        parts.append("")
        parts.append("</details>")
        parts.append("")
    parts.append("</details>")
    return "\n".join(parts)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: <terraform-docs output> | python wrap_terraform_module_doc.py <module-display-name>")
    raw = sys.stdin.read()
    sys.stdout.write(wrap(raw, sys.argv[1]) + "\n")


if __name__ == "__main__":
    main()
