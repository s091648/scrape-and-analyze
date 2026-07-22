"""Generate an exception catalog from backend/, src/, models/, shared/ via static AST analysis.

Does NOT import any project code (see specs/016-db-schema-brushup/research.md §11) — parses
each file's source text directly, the same static-analysis philosophy as
scripts/generate_db_schema.py and scripts/generate_uml.py.

Output:
  - site/public/guide/architecture/exceptions-data.json
"""
import ast
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ["backend", "src", "models", "shared"]
OUTPUT_DIR = REPO_ROOT / "site" / "public" / "guide" / "architecture"

# Framework exception types raised directly by name in this codebase. Anything not found
# here and not defined locally (see _resolve_custom_exceptions) is classified "builtin".
FRAMEWORK_EXCEPTION_NAMES = {"HTTPException"}
EXCEPTION_ROOTS = {"Exception", "BaseException"}


class ExceptionCatalogParseError(Exception):
    pass


@dataclass
class RaiseSite:
    file: str
    line: int
    function: str
    snippet: str
    status_code: int | None = None


@dataclass
class ExceptionInfo:
    name: str
    category: str
    bases: list = field(default_factory=list)
    docstring: str | None = None
    defined_at: dict | None = None
    raise_sites: list = field(default_factory=list)


def _iter_source_files():
    for dirname in SCAN_DIRS:
        base = REPO_ROOT / dirname
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            rel_parts = path.relative_to(REPO_ROOT).parts
            if "tests" in rel_parts or "__pycache__" in rel_parts:
                continue
            yield path


def _name_of(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _parse_file(path):
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        raise ExceptionCatalogParseError(f"{path}: failed to parse — {e}") from e
    return tree, source.splitlines()


# ─── Pass 1: collect class definitions (name → bases/file/line/docstring) ──────

def _collect_classes(tree, rel_path):
    classes = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = [b for b in (_name_of(base) for base in node.bases) if b]
            classes[node.name] = {
                "bases": bases,
                "file": rel_path,
                "line": node.lineno,
                "docstring": ast.get_docstring(node),
            }
    return classes


def _resolve_custom_exceptions(all_classes):
    """Fixed-point closure: direct Exception/BaseException subclasses, plus anything
    that transitively subclasses one of them (chains of locally-defined exceptions)."""
    custom = {
        name for name, info in all_classes.items()
        if any(b in EXCEPTION_ROOTS for b in info["bases"])
    }
    changed = True
    while changed:
        changed = False
        for name, info in all_classes.items():
            if name in custom:
                continue
            if any(b in custom for b in info["bases"]):
                custom.add(name)
                changed = True
    return custom


# ─── Pass 2: walk raise statements, resolving each to an exception type name ───

def _status_code_of(call_node):
    for kw in call_node.keywords:
        if kw.arg == "status_code" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, int):
            return kw.value.value
    return None


def _resolve_handler_type(handler):
    """None (bare `except:`) or a multi-type `except (A, B):` tuple is unresolvable."""
    if handler.type is None or isinstance(handler.type, ast.Tuple):
        return None
    return _name_of(handler.type)


def _resolve_raise(node, except_stack):
    """Returns (name, status_code); name is None if the raise is unresolvable."""
    exc = node.exc
    if exc is None:
        # Bare `raise` — Python syntax guarantees this is inside an except block.
        if not except_stack:
            return None, None
        return _resolve_handler_type(except_stack[-1]), None
    if isinstance(exc, ast.Call):
        name = _name_of(exc.func)
        status_code = _status_code_of(exc) if name == "HTTPException" else None
        return name, status_code
    if isinstance(exc, ast.Name):
        # `raise e` re-raising the bound except variable resolves via the handler's type.
        if except_stack and exc.id == except_stack[-1].name:
            return _resolve_handler_type(except_stack[-1]), None
        # Otherwise this Name is either a bare class reference (`raise SomeError`, no
        # parens — legal Python, and by convention UpperCamelCase) or a lowercase
        # variable holding a previously-caught exception instance under a name other
        # than the except binding (e.g. `raise last_403_exc` after a loop) — the latter
        # can't be resolved without data-flow tracing, so it's excluded rather than
        # misattributed, per the same principle as the unresolvable-re-raise edge case.
        if exc.id[:1].isupper():
            return exc.id, None
        return None, None
    if isinstance(exc, ast.Attribute):
        return exc.attr, None
    return None, None


def _walk_body(stmts, name_stack, except_stack, rel_path, source_lines, collector):
    for stmt in stmts:
        _walk_stmt(stmt, name_stack, except_stack, rel_path, source_lines, collector)


def _walk_stmt(stmt, name_stack, except_stack, rel_path, source_lines, collector):
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        name_stack.append(stmt.name)
        _walk_body(stmt.body, name_stack, except_stack, rel_path, source_lines, collector)
        name_stack.pop()
        return

    if isinstance(stmt, ast.Try):
        _walk_body(stmt.body, name_stack, except_stack, rel_path, source_lines, collector)
        for handler in stmt.handlers:
            except_stack.append(handler)
            _walk_body(handler.body, name_stack, except_stack, rel_path, source_lines, collector)
            except_stack.pop()
        _walk_body(stmt.orelse, name_stack, except_stack, rel_path, source_lines, collector)
        _walk_body(stmt.finalbody, name_stack, except_stack, rel_path, source_lines, collector)
        return

    if isinstance(stmt, ast.Raise):
        name, status_code = _resolve_raise(stmt, except_stack)
        if name:
            function = ".".join(name_stack) if name_stack else "<module>"
            snippet = (
                source_lines[stmt.lineno - 1].strip()
                if 0 < stmt.lineno <= len(source_lines) else ""
            )
            collector.append((name, RaiseSite(
                file=rel_path, line=stmt.lineno, function=function,
                snippet=snippet, status_code=status_code,
            )))
        return

    if isinstance(stmt, ast.Match):
        for case in stmt.cases:
            _walk_body(case.body, name_stack, except_stack, rel_path, source_lines, collector)
        return

    # Generic containers (If, For, While, With, AsyncFor, AsyncWith, ...): recurse into
    # any statement-list field (body/orelse/finalbody-shaped attributes).
    for _field_name, value in ast.iter_fields(stmt):
        if isinstance(value, list) and value and isinstance(value[0], ast.stmt):
            _walk_body(value, name_stack, except_stack, rel_path, source_lines, collector)


def generate():
    parsed = []
    all_classes = {}
    for path in _iter_source_files():
        tree, lines = _parse_file(path)
        rel_path = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        parsed.append((tree, rel_path, lines))
        all_classes.update(_collect_classes(tree, rel_path))

    custom_names = _resolve_custom_exceptions(all_classes)
    exceptions: dict[str, ExceptionInfo] = {}

    def _get_or_create(name):
        if name not in exceptions:
            if name in custom_names:
                info = all_classes[name]
                exceptions[name] = ExceptionInfo(
                    name=name, category="custom", bases=info["bases"],
                    docstring=info["docstring"],
                    defined_at={"file": info["file"], "line": info["line"]},
                )
            elif name in FRAMEWORK_EXCEPTION_NAMES:
                exceptions[name] = ExceptionInfo(name=name, category="framework")
            else:
                exceptions[name] = ExceptionInfo(name=name, category="builtin")
        return exceptions[name]

    for tree, rel_path, lines in parsed:
        collector = []
        _walk_body(tree.body, [], [], rel_path, lines, collector)
        for name, site in collector:
            _get_or_create(name).raise_sites.append(site)

    return {"exceptions": [asdict(exceptions[name]) for name in sorted(exceptions)]}


def main():
    result = generate()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "exceptions-data.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_path} ({len(result['exceptions'])} exception types)")


if __name__ == "__main__":
    main()
