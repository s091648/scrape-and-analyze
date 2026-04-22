#!/usr/bin/env python3
"""
Preprocesses a pg_dump plain-SQL file for idempotent re-application:
  - CREATE TABLE → CREATE TABLE IF NOT EXISTS
  - CREATE [UNIQUE] INDEX → CREATE [UNIQUE] INDEX IF NOT EXISTS
  - COPY ... FROM stdin blocks → INSERT ... ON CONFLICT DO NOTHING

All DDL is emitted first, then data is emitted in FK-safe dependency order
so that referenced tables (e.g. articles) are always inserted before tables
that reference them (e.g. analyses).
"""
import sys
import re

# Tables emitted in this priority order (lowest index = first).
# Any table not listed is emitted after all listed ones.
TABLE_PRIORITY = [
    "public.articles",
    "public.failed_tasks",
    "public.analyses",
]


def priority_key(table_name: str) -> int:
    normalized = table_name.lower()
    for i, p in enumerate(TABLE_PRIORITY):
        table_part = p.split(".")[-1]  # e.g., "articles" from "public.articles"
        if normalized == p or normalized == table_part or normalized.endswith("." + table_part):
            return i
    return len(TABLE_PRIORITY)


def unescape_copy_field(v: str) -> str:
    """Unescape a PostgreSQL COPY text-format field and return a SQL literal."""
    if v == "\\N":
        return "NULL"
    result = []
    i = 0
    while i < len(v):
        if v[i] == "\\" and i + 1 < len(v):
            c = v[i + 1]
            if c == "n":
                result.append("\n")
            elif c == "t":
                result.append("\t")
            elif c == "r":
                result.append("\r")
            elif c == "\\":
                result.append("\\")
            else:
                result.append(c)
            i += 2
        else:
            result.append(v[i])
            i += 1
    return "'" + "".join(result).replace("'", "''") + "'"


def main():
    ddl_lines: list[str] = []
    # table_name → list of INSERT strings
    table_inserts: dict[str, list[str]] = {}
    table_order: list[str] = []

    in_copy = False
    current_table = ""
    headers: list[str] = []

    for line in sys.stdin:
        if in_copy:
            stripped = line.rstrip("\n")
            if stripped == "\\.":
                in_copy = False
            else:
                values = stripped.split("\t")
                escaped = [unescape_copy_field(v) for v in values]
                insert = (
                    f"INSERT INTO {current_table} ({', '.join(headers)}) "
                    f"VALUES ({', '.join(escaped)}) ON CONFLICT DO NOTHING;"
                )
                table_inserts[current_table].append(insert)
        else:
            m = re.match(r"COPY (\S+) \(([^)]+)\) FROM stdin;", line)
            if m:
                current_table = m.group(1)
                headers = [h.strip() for h in m.group(2).split(",")]
                in_copy = True
                if current_table not in table_inserts:
                    table_inserts[current_table] = []
                    table_order.append(current_table)
            elif line.startswith("CREATE UNIQUE INDEX "):
                ddl_lines.append(
                    line.replace("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS ", 1)
                )
            elif line.startswith("CREATE INDEX "):
                ddl_lines.append(
                    line.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1)
                )
            elif line.startswith("CREATE TABLE "):
                ddl_lines.append(
                    line.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)
                )
            else:
                ddl_lines.append(line)

    # Emit DDL first
    sys.stdout.writelines(ddl_lines)

    # Emit data in FK-safe order
    ordered = sorted(table_order, key=priority_key)
    for table in ordered:
        for insert in table_inserts[table]:
            print(insert)


if __name__ == "__main__":
    main()
