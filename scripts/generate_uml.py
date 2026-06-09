"""Generate UML class diagram data from src/ using pyreverse.

Outputs:
  - site/public/guide/architecture/classes.dot  (raw Graphviz dot)
  - site/public/guide/architecture/packages.dot  (package-level dot)
  - site/public/guide/architecture/uml-data.json (structured data for Vue components)
"""

import ast
import json
import re
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
OUTPUT_DIR = REPO_ROOT / "site" / "public" / "guide" / "architecture"

# Layer classification based on pyreverse node ID prefixes.
# pyreverse strips the src.modules.xxx prefix, so we match on what it actually outputs.
LAYER_RULES = [
    # ── Precise rules (^ anchor, short pyreverse IDs) ─────────────────────────
    # Domain layer
    (r"^(domain\.(entities|repositories|value_objects|services|factories|events))\.", "domain"),
    (r"^(entities\.|repositories\.|value_objects\.|services\.)", "domain"),
    # Application layer
    (r"^(application\.(events|event_handlers|use_cases|dtos|ports))\.", "application"),
    (r"^(use_cases\.|event_handlers\.)", "application"),
    # Infrastructure — collection
    (r"^(scrapers\.|clients\.|executor\.|parsers\.|collection\.)", "infrastructure-collection"),
    (r"^(collection_pipeline|handlers\.)", "infrastructure-collection"),
    # Infrastructure — persistence
    (r"^(shared\.(article_repo_impl|failed_task_repo_impl|topic_repo_impl))\.", "infrastructure-persistence"),
    (r"^(intelligence\.(analysis_repo_impl|tag_repo_impl|tag_translation_repo_impl|analyses_translation_repo_impl|tag_group_definition_repo_impl))\.", "infrastructure-persistence"),
    (r"^(collection\.(arxiv_metadata_repo_impl|scraper_setting_repo_impl))\.", "infrastructure-persistence"),
    # Infrastructure — LLM / intelligence
    (r"^(llm\.|prompt\.|factories\.prompt_factory)", "infrastructure-intelligence"),
    # Infrastructure — shared
    (r"^(notifications\.|events\.in_memory_event_bus|events\.pipeline_completed)", "infrastructure-shared"),
    # Entrypoints
    (r"^entrypoints\.", "entrypoints"),
    # Shared application
    (r"^(application\.ports|application\.events)\.", "shared-application"),
    (r"^events\.(article_processed|analysis_completed|analysis_failed|article_scraped|failed|tag_normalization|translation_failed|pipeline_completed|in_memory_event_bus)", "shared-application"),
    # Config
    (r"^config\.", "config"),

    # ── Flexible fallback rules (no ^ anchor, match module-prefixed paths) ────
    # These handle full paths like modules.collection.domain.events.X produced by
    # some pyreverse versions that don't strip the src.modules.* prefix.
    (r"\bdomain\.(entities|repositories|value_objects|services|factories|events)\.", "domain"),
    (r"\b(entities|repositories|value_objects|services)\.", "domain"),
    (r"\bapplication\.(events|event_handlers|use_cases|dtos|ports)\.", "application"),
    (r"\b(use_cases|event_handlers)\.", "application"),
    (r"\b(scrapers?|clients?|parsers?|executor)\.", "infrastructure-collection"),
    (r"\bllm\.", "infrastructure-intelligence"),
    (r"\bprompt\.", "infrastructure-intelligence"),
    (r"\bnotifications?\.", "infrastructure-shared"),
    (r"_repo_impl\b", "infrastructure-persistence"),
    (r"\bentrypoints?\.", "entrypoints"),
    (r"\bconfig\.", "config"),
]

# Layer display order and colors for dot subgraphs
LAYER_DISPLAY = [
    ("entrypoints", "entrypoints", "#e94560"),
    ("application", "application", "#44BB99"),
    ("domain", "domain", "#77AADD"),
    ("shared-application", "shared-app", "#99DDFF"),
    ("infrastructure-collection", "infra-collection", "#BBCC33"),
    ("infrastructure-persistence", "infra-persistence", "#AAAA00"),
    ("infrastructure-intelligence", "infra-intelligence", "#EEDD88"),
    ("infrastructure-shared", "infra-shared", "#EE8866"),
    ("config", "config", "#DDDDDD"),
]

# Maps fine-grained layer → one of 4 Clean Architecture circles
CA_LAYER_MAP = {
    "domain": "entities",
    "application": "application",
    "shared-application": "application",
    "infrastructure-persistence": "adapters",
    "entrypoints": "adapters",
    "infrastructure-collection": "infrastructure",
    "infrastructure-intelligence": "infrastructure",
    "infrastructure-shared": "infrastructure",
    "config": "infrastructure",
    "unknown": "infrastructure",
}

# 4 CA circles in display order (infrastructure outermost, entities innermost)
CA_CIRCLE_META = [
    ("infrastructure", "Infrastructure",     "#BBCC33"),
    ("adapters",       "Interface Adapters", "#EEDD88"),
    ("application",    "Application",        "#44BB99"),
    ("entities",       "Domain / Entities",  "#77AADD"),
]

# Rules to classify a node into a subgroup within its CA circle
SUBGROUP_RULES = [
    (r"(^|\.)entities\.",         "entities"),
    (r"(^|\.)value_objects\.",    "value_objects"),
    (r"(^|\.)repositories\.",     "repositories"),
    (r"(^|\.)services\.",         "domain_services"),
    (r"(^|\.)factories\.",        "factories"),
    # events must come before event_handlers (more specific, no trailing dot ambiguity)
    (r"(^|\.)domain\.events\.",   "events"),
    (r"(^|\.)events\.",           "events"),
    (r"(^|\.)use_cases\.",        "use_cases"),
    (r"use_case\b",               "use_cases"),
    (r"(^|\.)event_handlers\.",   "event_handlers"),
    (r"handler\b",                "event_handlers"),
    (r"(^|\.)ports\.",            "ports"),
    (r"(^|\.)dtos\.",             "dtos"),
    (r"(^|\.)scrapers?\.",        "scrapers"),
    (r"(^|\.)clients?\.",         "clients"),
    (r"(^|\.)parsers?\.",         "parsers"),
    (r"(^|\.)executor\.",         "executor"),
    (r"(^|\.)llm\.",              "llm"),
    (r"(^|\.)prompt\.",           "prompt"),
    (r"(^|\.)notifications?\.",   "notifications"),
    (r"_repo_impl\b",             "persistence"),
    (r"(^|\.)entrypoints?\.",     "entrypoints"),
    (r"(^|\.)config\.",           "config"),
]

SUBGROUP_LABELS = {
    "entities": "Entities",
    "value_objects": "Value Objects",
    "repositories": "Repositories",
    "domain_services": "Domain Services",
    "factories": "Factories",
    "use_cases": "Use Cases",
    "event_handlers": "Event Handlers",
    "ports": "Ports",
    "dtos": "DTOs",
    "scrapers": "Scrapers",
    "clients": "Clients",
    "parsers": "Parsers",
    "executor": "Executor",
    "llm": "LLM Providers",
    "prompt": "Prompt",
    "notifications": "Notifications",
    "persistence": "Persistence",
    "entrypoints": "Entrypoints",
    "config": "Config",
    "events": "Events",
    "other": "Other",
    "collection": "Collection",
    "intelligence": "Intelligence",
    "shared": "Shared",
}

# Context (usage-scenario) grouping — auto-detected from src/modules/ + fixed infrastructure contexts.
# Adding a new directory under src/modules/ automatically adds a context rule and label.

def _build_context_rules() -> list[tuple[str, str]]:
    """Scan src/modules/ to build context rules. notifications must precede shared."""
    module_rules: list[tuple[str, str]] = []
    modules_dir = SRC_DIR / "modules"
    if modules_dir.exists():
        for d in sorted(modules_dir.iterdir()):
            if d.is_dir() and not d.name.startswith("_"):
                module_rules.append((rf"\b{d.name}\b", d.name))
    return [
        (r"\bnotifications\b", "notifications"),  # before shared: lives in infrastructure/shared/notifications/
        *module_rules,
        (r"\bshared\b",        "shared"),
        (r"\bentrypoints\b",   "entrypoints"),
        (r"\bconfig\b",        "config"),
        (r"\bbootstrap\b",     "bootstrap"),
    ]


def _build_context_labels() -> dict[str, str]:
    """Generate display labels for all known contexts, including auto-detected modules."""
    labels: dict[str, str] = {
        "notifications": "Notifications",
        "shared":        "Shared",
        "entrypoints":   "Entrypoints",
        "config":        "Config",
        "bootstrap":     "Bootstrap",
        "other":         "Other",
    }
    modules_dir = SRC_DIR / "modules"
    if modules_dir.exists():
        for d in modules_dir.iterdir():
            if d.is_dir() and not d.name.startswith("_"):
                labels[d.name] = d.name.title()
    return labels


CONTEXT_RULES  = _build_context_rules()
CONTEXT_LABELS = _build_context_labels()


def classify_layer(node_id: str) -> str:
    for pattern, layer in LAYER_RULES:
        if re.search(pattern, node_id):
            return layer
    return "unknown"


def classify_context(node_id: str, source_file: str = "") -> str:
    """Classify a node into a business/feature context (collection, intelligence, shared…).

    Prefers source_file (full path like src/modules/collection/...) over node_id because
    pyreverse strips the modules.* prefix, making node IDs like 'entities.article.Article'
    which lose the collection/intelligence context.
    """
    path = source_file or node_id
    for pattern, context in CONTEXT_RULES:
        if re.search(pattern, path):
            return context
    return "other"


def classify_subgroup(node_id: str, layer: str) -> str:
    for pattern, group in SUBGROUP_RULES:
        if re.search(pattern, node_id):
            return group
    # Fallback: use the last segment of the infrastructure sub-layer name
    if layer.startswith("infrastructure-"):
        return layer.replace("infrastructure-", "")
    return "other"


def _fmt_annotation(ann_node) -> str:
    try:
        return ast.unparse(ann_node)
    except Exception:
        return "..."


def _fmt_method_sig(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = []
    for arg in func_node.args.args:
        if arg.arg == "self":
            continue
        if arg.annotation:
            args.append(f"{arg.arg}: {_fmt_annotation(arg.annotation)}")
        else:
            args.append(arg.arg)
    if func_node.args.vararg:
        v = func_node.args.vararg
        args.append(f"*{v.arg}: {_fmt_annotation(v.annotation)}" if v.annotation else f"*{v.arg}")
    for kw in func_node.args.kwonlyargs:
        args.append(f"{kw.arg}: {_fmt_annotation(kw.annotation)}" if kw.annotation else kw.arg)
    if func_node.args.kwarg:
        k = func_node.args.kwarg
        args.append(f"**{k.arg}: {_fmt_annotation(k.annotation)}" if k.annotation else f"**{k.arg}")
    ret = f" → {_fmt_annotation(func_node.returns)}" if func_node.returns else ""
    prefix = "async " if isinstance(func_node, ast.AsyncFunctionDef) else ""
    return f"{prefix}{func_node.name}({', '.join(args)}){ret}"


def _extract_self_attrs(class_node: ast.ClassDef) -> list[str]:
    """Extract self.x attributes from __init__ — annotated and untyped."""
    seen: set[str] = set()
    result: list[str] = []
    for stmt in class_node.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) or stmt.name != "__init__":
            continue
        for sub in ast.walk(stmt):
            # Annotated: self.x: Type = val
            if isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Attribute):
                if isinstance(sub.target.value, ast.Name) and sub.target.value.id == "self":
                    name = sub.target.attr
                    if name not in seen:
                        seen.add(name)
                        result.append(f"{name}: {_fmt_annotation(sub.annotation)}")
            # Untyped: self.x = val
            elif isinstance(sub, ast.Assign):
                for t in sub.targets:
                    if (isinstance(t, ast.Attribute)
                            and isinstance(t.value, ast.Name)
                            and t.value.id == "self"):
                        if t.attr not in seen:
                            seen.add(t.attr)
                            result.append(t.attr)
    return result


_INCLUDE_DUNDERS = {"__init__", "__str__", "__repr__", "__call__", "__len__",
                    "__iter__", "__next__", "__enter__", "__exit__", "__aenter__", "__aexit__"}


def build_class_ast_data() -> dict[str, dict]:
    """Scan all Python source files; return class_name → AST-derived info."""
    result: dict[str, dict] = {}
    for py_file in collect_py_files():
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        rel_path = str(py_file.relative_to(REPO_ROOT))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            docstring = ast.get_docstring(node) or ""
            # Truncate docstring to first sentence(s), max 200 chars
            if docstring and len(docstring) > 200:
                docstring = docstring[:200].rsplit(" ", 1)[0] + "…"
            # Class-body type annotations (e.g. `name: str`)
            class_attrs = []
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    class_attrs.append(f"{stmt.target.id}: {_fmt_annotation(stmt.annotation)}")
            # self.x: Type from __init__
            init_attrs = _extract_self_attrs(node)
            # Methods (as {sig, doc} objects so the Vue viewer can show docstrings)
            methods = []
            for stmt in node.body:
                if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if stmt.name.startswith("__") and stmt.name not in _INCLUDE_DUNDERS:
                    continue
                try:
                    sig = _fmt_method_sig(stmt)
                except Exception:
                    sig = stmt.name
                method_doc = ast.get_docstring(stmt) or ""
                if method_doc and len(method_doc) > 160:
                    method_doc = method_doc[:160].rsplit(" ", 1)[0] + "…"
                methods.append({"sig": sig, "doc": method_doc})
            typed_attrs = class_attrs or init_attrs
            result[node.name] = {
                "docstring": docstring,
                "typed_attrs": typed_attrs,
                "typed_methods": methods,
                "source_file": rel_path,
            }
    return result


def collect_py_files() -> list[Path]:
    """Collect all .py files in src/ except tests and __init__."""
    files = []
    for f in SRC_DIR.rglob("*.py"):
        rel = f.relative_to(SRC_DIR)
        if any(part == "tests" for part in rel.parts):
            continue
        if any(part == "__pycache__" for part in rel.parts):
            continue
        if f.name == "__init__.py":
            continue
        files.append(f)
    return sorted(files)


def build_file_to_module_map() -> dict[str, str]:
    """Map relative file paths to their full module paths for layer classification."""
    mapping = {}
    for f in SRC_DIR.rglob("*.py"):
        rel = f.relative_to(SRC_DIR)
        if any(part == "tests" for part in rel.parts):
            continue
        if any(part == "__pycache__" for part in rel.parts):
            continue
        # Convert path like modules/collection/domain/entities/article.py
        # to src.modules.collection.domain.entities.article
        module = "src." + str(rel.with_suffix("")).replace("/", ".")
        mapping[str(f)] = module
    return mapping


def parse_dot_file(dot_path: Path) -> dict:
    """Parse a .dot file into structured nodes and edges."""
    content = dot_path.read_text()

    nodes = []
    edges = []

    node_pattern = re.compile(
        r'^\s*"([^"]+)"\s+\[([^]]+)\]',
        re.MULTILINE,
    )
    edge_pattern = re.compile(
        r'^\s*"([^"]+)"\s*->\s*"([^"]+)"\s+\[([^]]+)\]',
        re.MULTILINE,
    )

    for match in node_pattern.finditer(content):
        node_id = match.group(1)
        attrs_str = match.group(2)
        attrs = _parse_attrs(attrs_str)
        nodes.append({"id": node_id, **attrs})

    for match in edge_pattern.finditer(content):
        source = match.group(1)
        target = match.group(2)
        attrs_str = match.group(3)
        attrs = _parse_attrs(attrs_str)
        edge_type = _classify_edge(attrs)
        edges.append({"source": source, "target": target, "type": edge_type, **attrs})

    return {"nodes": nodes, "edges": edges}


def _parse_attrs(attrs_str: str) -> dict:
    """Parse dot attribute string."""
    attrs = {}
    for part in re.findall(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)', attrs_str):
        key, val = part
        val = val.strip('"')
        attrs[key] = val
    return attrs


def _classify_edge(attrs: dict) -> str:
    arrowtail = attrs.get("arrowtail", "")
    arrowhead = attrs.get("arrowhead", "")
    style = attrs.get("style", "")

    if "empty" in arrowhead or "onormal" in arrowtail:
        return "inheritance"
    if "diamond" in arrowtail:
        return "composition"
    if "odiamond" in arrowtail:
        return "aggregation"
    if style == "dashed":
        return "dependency"
    return "association"


def _parse_label(label: str) -> dict:
    """Parse pyreverse record label into attributes and methods."""
    result = {"class_name": "", "attributes": [], "methods": []}

    if not label:
        return result

    # Strip HTML tags: <{ ... }> → extract text content
    clean = re.sub(r"<[^>]*>", "", label)
    # Remove stray braces from HTML-like labels
    clean = clean.replace("{", "").replace("}", "")

    # pyreverse labels: "ClassName|attr1\\nattr2|method1\\nmethod2"
    parts = clean.split("|")
    result["class_name"] = parts[0].strip()

    if len(parts) > 1:
        attrs_raw = parts[1].strip()
        if attrs_raw:
            result["attributes"] = [a.strip() for a in attrs_raw.split("\\n") if a.strip()]

    if len(parts) > 2:
        methods_raw = parts[2].strip()
        if methods_raw:
            result["methods"] = [m.strip() for m in methods_raw.split("\\n") if m.strip()]

    return result


def run_pyreverse(py_files: list[Path]) -> bool:
    """Run pyreverse with explicit .py file paths."""
    for f in OUTPUT_DIR.glob("*.dot"):
        f.unlink()

    # Resolve pyreverse from the same venv as the running Python, falling back to PATH
    pyreverse_bin = Path(sys.executable).parent / "pyreverse"
    pyreverse_cmd = str(pyreverse_bin) if pyreverse_bin.exists() else "pyreverse"

    cmd = [
        pyreverse_cmd,
        *[str(f) for f in py_files],
        "-o", "dot",
        "-p", "ScrapeAnalyzer",
        "-d", str(OUTPUT_DIR),
        "-f", "ALL",
    ]

    print(f"Running pyreverse with {len(py_files)} files...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    print(f"pyreverse returncode: {result.returncode}")
    if result.stdout:
        print(f"pyreverse stdout:\n{result.stdout}")
    if result.stderr:
        print(f"pyreverse stderr:\n{result.stderr}", file=sys.stderr)

    if result.returncode != 0:
        return False

    print("pyreverse completed successfully")
    return True


def rebuild_dot_with_layers(dot_path: Path) -> None:
    """Rewrite the dot file to add subgraph clustering by layer and LR layout."""
    content = dot_path.read_text()

    # Parse all node IDs
    node_pattern = re.compile(r'^\s*"([^"]+)"\s+\[', re.MULTILINE)
    node_ids = [m.group(1) for m in node_pattern.finditer(content)]

    # Classify nodes into layer buckets
    layer_nodes: dict[str, list[str]] = {}
    for nid in node_ids:
        layer = classify_layer(nid)
        layer_nodes.setdefault(layer, []).append(nid)

    # Read original dot content lines
    lines = content.split("\n")

    # Build new dot with subgraphs
    new_lines = []
    header_done = False
    for line in lines:
        new_lines.append(line)
        if not header_done and line.strip().startswith("charset"):
            # Insert layout changes after header
            new_lines.append('  rankdir=LR')
            new_lines.append('  splines=ortho')
            new_lines.append('  nodesep=0.4')
            new_lines.append('  ranksep=1.2')
            new_lines.append('  fontsize=12')
            new_lines.append('')
            # Add layer subgraphs
            for layer_key, layer_label, layer_color in LAYER_DISPLAY:
                if layer_key in layer_nodes:
                    new_lines.append(f'  subgraph "cluster_{layer_key}" {{')
                    new_lines.append(f'    label="{layer_label}"')
                    new_lines.append(f'    style=filled')
                    new_lines.append(f'    color="{layer_color}"')
                    new_lines.append(f'    fillcolor="{layer_color}15"')
                    new_lines.append(f'    fontcolor="{layer_color}"')
                    for nid in layer_nodes[layer_key]:
                        new_lines.append(f'    "{nid}"')
                    new_lines.append('  }')
                    new_lines.append('')
            header_done = True

    dot_path.write_text("\n".join(new_lines))


# ── Pipeline inference helpers ──────────────────────────────────────────────────

def _find_pipeline_func(tree: ast.AST) -> ast.FunctionDef | None:
    """Return the top-level function with the most event_bus.subscribe() calls.

    Avoids hardcoding 'build_collection_pipeline' — works for any future
    pipeline builder function name as long as it wires handlers via subscribe().
    """
    best_func: ast.FunctionDef | None = None
    best_count = 0
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        count = sum(
            1 for sub in ast.walk(fn)
            if (isinstance(sub, ast.Call)
                and isinstance(getattr(sub.func, "attr", None), str)
                and sub.func.attr == "subscribe")
        )
        if count > best_count:
            best_count = count
            best_func = fn
    return best_func if best_count > 0 else None


def _call_class_name(call_node: ast.Call) -> str | None:
    """Return the class/function name from a Call node, or None if unresolvable."""
    if isinstance(call_node.func, ast.Name):
        return call_node.func.id
    if isinstance(call_node.func, ast.Attribute):
        return call_node.func.attr
    return None


def _build_func_return_map() -> dict[str, str]:
    """Scan all src/ Python files and return {func_name: ReturnClassName} for annotated functions."""
    result: dict[str, str] = {}
    for py_file in collect_py_files():
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except Exception:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.returns:
                continue
            # Only capture simple Name returns like "-> HttpClient"
            if isinstance(node.returns, ast.Name) and node.returns.id[0].isupper():
                result[node.name] = node.returns.id
            # Also capture Optional[X] / X | None patterns — just take the class name
            elif isinstance(node.returns, ast.BinOp):
                # X | None
                left = node.returns.left
                if isinstance(left, ast.Name) and left.id[0].isupper():
                    result.setdefault(node.name, left.id)
    return result


def _build_class_creates_map() -> dict[str, list[str]]:
    """For each class, collect the UpperCase classes it instantiates anywhere in its body.

    Used to augment the DI tree for factory classes that create objects dynamically
    (e.g. ConcreteScraperFactory.create_for() instantiating RssScraper, ArxivScraper…).
    Only captures direct `ClassName(...)` calls — not method-chained or nested ones.
    """
    result: dict[str, list[str]] = {}
    for py_file in collect_py_files():
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except Exception:
            continue
        for class_node in ast.walk(tree):
            if not isinstance(class_node, ast.ClassDef):
                continue
            created: list[str] = []
            seen: set[str] = set()
            for sub in ast.walk(class_node):
                if not isinstance(sub, ast.Call):
                    continue
                cls_name = _call_class_name(sub)
                if cls_name and cls_name[0].isupper() and cls_name != class_node.name:
                    if cls_name not in seen:
                        seen.add(cls_name)
                        created.append(cls_name)
            if created:
                result[class_node.name] = created
    return result


def _find_handle_attr(
    node: ast.expr, var_to_class: dict[str, str]
) -> tuple[str | None, str | None]:
    """Walk an expression tree to find <var>.handle and return (var_name, class_name).

    Handles the common pattern where the handler is wrapped in with_span(..., var.handle, ...),
    with_span_deferred(..., var.handle, ...), etc.
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr == "handle":
            if isinstance(sub.value, ast.Name):
                var_name = sub.value.id
                return var_name, var_to_class.get(var_name)
    return None, None


def _build_class_publish_map() -> dict[str, list[str]]:
    """
    Scan all src/ Python files.  For each class that has a ``handle()`` method,
    record the event class names passed to ``*.publish(EventClass(...))`` calls.
    """
    publish_map: dict[str, list[str]] = {}
    for py_file in collect_py_files():
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except Exception:
            continue
        for class_node in ast.walk(tree):
            if not isinstance(class_node, ast.ClassDef):
                continue
            published: list[str] = []
            for method in class_node.body:
                if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if method.name != "handle":
                    continue
                for stmt_node in ast.walk(method):
                    if not (
                        isinstance(stmt_node, ast.Call)
                        and isinstance(stmt_node.func, ast.Attribute)
                        and stmt_node.func.attr == "publish"
                        and stmt_node.args
                    ):
                        continue
                    first_arg = stmt_node.args[0]
                    if isinstance(first_arg, ast.Call):
                        ec = _call_class_name(first_arg)
                        if ec:
                            published.append(ec)
                    elif isinstance(first_arg, ast.Name):
                        published.append(first_arg.id)
            if published:
                publish_map[class_node.name] = published
    return publish_map


def _build_di_tree(
    var_name: str,
    var_to_class: dict[str, str],
    var_to_kwargs_vars: dict[str, list],
    class_creates_map: dict[str, list[str]] | None = None,
    visited: frozenset | None = None,
    depth: int = 0,
) -> list[dict]:
    """Recursively build a DI dependency tree for *var_name*.

    Each node: {"param": kwarg_name, "class": ClassName, "deps": [...]}

    Bootstrap kwargs are followed first (explicit DI).  When a class has no
    bootstrap kwargs (depth > 0), class_creates_map supplements it with
    classes the implementation instantiates internally (factory pattern).
    """
    if visited is None:
        visited = frozenset()
    if var_name in visited or depth > 6:
        return []
    visited = visited | {var_name}
    result = []

    # --- Explicit bootstrap DI (always preferred) ---
    explicit_deps = var_to_kwargs_vars.get(var_name, [])
    seen_cls: set[str] = set()
    for dep in explicit_deps:
        dep_var  = dep["var"]   if isinstance(dep, dict) else dep
        param    = dep["param"] if isinstance(dep, dict) else ""
        dep_cls  = var_to_class.get(dep_var, "")
        if not dep_cls or not dep_cls[0].isupper():
            continue
        seen_cls.add(dep_cls)
        children = _build_di_tree(dep_var, var_to_class, var_to_kwargs_vars, class_creates_map, visited, depth + 1)
        result.append({"param": param, "class": dep_cls, "deps": children})

    # --- Implicit / factory instantiations (supplement when no bootstrap deps) ---
    # Only inject class_creates_map at depth > 0 so the pipeline root isn't exploded.
    if class_creates_map and depth > 0:
        own_cls = var_to_class.get(var_name, "")
        for created_cls in class_creates_map.get(own_cls, []):
            if created_cls in seen_cls or created_cls in visited:
                continue
            # Skip stdlib/third-party primitives and domain value objects
            skip_exact = {
                # stdlib concurrency
                "Lock", "Semaphore", "RLock", "Thread", "BoundedSemaphore",
                "Queue", "ThreadPoolExecutor",
                # third-party
                "BeautifulSoup", "Response", "Tag", "Session",
                # internal helpers
                "Logger",
                # domain entities / value objects (not infrastructure)
                "ScrapedArticle", "ScrapeJob", "Article", "Analysis",
                "ScraperSetting", "ArticleModel", "SourceStats",
            }
            skip_suffix = (
                "Event", "Dto", "Result", "Error", "Exception",
                "Entry", "Model",  # ORM models
            )
            if created_cls in skip_exact:
                continue
            if any(created_cls.endswith(p) for p in skip_suffix):
                continue
            seen_cls.add(created_cls)
            # Synthesize a temporary var for recursion
            syn = f"_creates_{created_cls}"
            if syn not in var_to_class:
                var_to_class[syn] = created_cls
                var_to_kwargs_vars[syn] = []
            children = _build_di_tree(syn, var_to_class, var_to_kwargs_vars, class_creates_map, visited, depth + 1)
            result.append({"param": "creates", "class": created_cls, "deps": children})

    return result


def _infer_stage_icon(class_name: str) -> str:
    """Infer a stage icon from handler class name patterns — no hardcoded class names."""
    n = class_name.lower()
    if any(k in n for k in ("scraped", "scraper", "fetch", "collect")):  return "📄"
    if any(k in n for k in ("process", "analyz", "llm", "intelligence")): return "🧠"
    if any(k in n for k in ("normaliz", "tag")):                          return "🏷️"
    if any(k in n for k in ("translat",)):                                return "🌐"
    if any(k in n for k in ("metric", "otel", "telemetry", "monitor")):  return "📊"
    if any(k in n for k in ("notif",)):                                   return "📢"
    if any(k in n for k in ("failed", "persist", "error", "retry")):     return "⚠️"
    return "⚙️"


_STAGE_COLORS = ["#EEDD88", "#44BB99", "#44BB99", "#77AADD", "#EE8866", "#EE8866"]
# Classes to skip when listing "related use cases" per stage
_RELATED_SKIP = {"InMemoryEventBus", "PipelineStats", "FakeBus"}


def _camel_to_label(name: str) -> str:
    """ArticleScrapedHandler → Article Scraped (strips trailing Handler)."""
    words = re.sub(r"([A-Z])", r" \1", name).strip().split()
    if words and words[-1] == "Handler":
        words = words[:-1]
    return " ".join(words)


def build_pipeline_from_bootstrap() -> list[dict]:
    """
    Automatically infer the scraper pipeline by parsing src/bootstrap.py with AST.

    Steps
    -----
    1.  Parse build_collection_pipeline():
        - variable assignments  →  var_name: class_name
        - keyword args per var  →  var_name: [kwarg_var_name, ...]
    2.  Find event_bus.subscribe(EventClass, *.handle) calls
        →  {EventClass: HandlerClass}
    3.  For each handler class, scan its handle() method for *.publish(EventClass(...))
        →  {HandlerClass: [emitted_events]}
    4.  Topological BFS from entry events → ordered stage list
    5.  Prepend the CollectionPipeline "step 0" entry point.
    """
    bootstrap_path = SRC_DIR / "bootstrap.py"
    if not bootstrap_path.exists():
        print("WARNING: src/bootstrap.py not found — skipping pipeline inference", file=sys.stderr)
        return []

    try:
        source = bootstrap_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception as exc:
        print(f"WARNING: Failed to parse bootstrap.py: {exc}", file=sys.stderr)
        return []

    # ── 1. Find the pipeline builder function (most subscribe() calls wins) ─────
    pipeline_func = _find_pipeline_func(tree)
    if pipeline_func is None:
        return []

    var_to_class: dict[str, str] = {}          # var_name → ClassName
    var_to_kwargs_vars: dict[str, list[str]] = {}  # var_name → [kwarg var names]

    # Build helper maps for resolving function-call kwargs and factory instantiations
    func_return_map   = _build_func_return_map()    # func_name → ReturnClass
    class_creates_map = _build_class_creates_map()  # ClassName → [CreatedClass, ...]

    _synthetic_seq = [0]  # mutable counter for unique synthetic var names

    def _synthetic_var(prefix: str) -> str:
        _synthetic_seq[0] += 1
        return f"_syn_{prefix}_{_synthetic_seq[0]}"

    for node in ast.walk(pipeline_func):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            var_name = target.id
            if not isinstance(node.value, ast.Call):
                continue
            cls = _call_class_name(node.value)
            if cls:
                var_to_class[var_name] = cls
                # Capture both positional args (param="") and keyword args.
                pos_deps = [
                    {"param": "", "var": arg.id}
                    for arg in node.value.args
                    if isinstance(arg, ast.Name)
                ]
                kw_deps = [
                    {"param": kw.arg, "var": kw.value.id}
                    for kw in node.value.keywords
                    if isinstance(kw.value, ast.Name) and kw.arg is not None
                ]
                # Also handle function-call kwargs like http_client=get_default_client()
                fn_call_deps = []
                for kw in node.value.keywords:
                    if not (isinstance(kw.value, ast.Call) and kw.arg is not None):
                        continue
                    fn_name = _call_class_name(kw.value)
                    if fn_name and fn_name in func_return_map:
                        syn = _synthetic_var(fn_name)
                        var_to_class[syn] = func_return_map[fn_name]
                        var_to_kwargs_vars[syn] = []
                        fn_call_deps.append({"param": kw.arg, "var": syn})
                var_to_kwargs_vars[var_name] = pos_deps + kw_deps + fn_call_deps

    # ── 2. Extract subscribe calls ────────────────────────────────────────────
    # List of {event, handler_class, handler_var}
    subscriptions: list[dict[str, str]] = []

    for node in ast.walk(pipeline_func):
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
            continue
        call = node.value
        if not (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "subscribe"
            and len(call.args) >= 2
        ):
            continue
        event_arg = call.args[0]
        if not isinstance(event_arg, ast.Name):
            continue
        event_class = event_arg.id
        handler_var, handler_class = _find_handle_attr(call.args[1], var_to_class)
        if handler_class and handler_class[0].isupper():
            # Skip factory functions (lowercase first char) like build_notification_handler()
            subscriptions.append({
                "event": event_class,
                "handler_class": handler_class,
                "handler_var": handler_var or "",
            })

    if not subscriptions:
        return []

    print(f"Pipeline: found {len(subscriptions)} event subscriptions in bootstrap.py")

    # ── 3. Scan handler sources for published events ───────────────────────────
    class_publish_map = _build_class_publish_map()

    # ── 4. Build helper maps ──────────────────────────────────────────────────
    # event → [handler_class, ...]  (multiple handlers can subscribe to same event)
    event_to_handlers: dict[str, list[str]] = {}
    for s in subscriptions:
        event_to_handlers.setdefault(s["event"], []).append(s["handler_class"])

    # handler_class → [related use case class names from constructor kwargs]
    handler_related: dict[str, list[str]] = {}
    for s in subscriptions:
        hc = s["handler_class"]
        if hc in handler_related:
            continue
        related: list[str] = []
        for dep in var_to_kwargs_vars.get(s["handler_var"], []):
            dep_var = dep["var"] if isinstance(dep, dict) else dep
            kc = var_to_class.get(dep_var)
            if kc and kc not in _RELATED_SKIP and kc != hc:
                related.append(kc)
        handler_related[hc] = related

    # Reverse map for DI tree: ClassName → var_name (last assignment wins)
    class_to_var: dict[str, str] = {
        cls: var for var, cls in var_to_class.items() if cls and cls[0].isupper()
    }

    # ── 5. Topological BFS ───────────────────────────────────────────────────
    all_handler_publishes = {
        ev for hc, evs in class_publish_map.items()
        if hc in {s["handler_class"] for s in subscriptions}
        for ev in evs
    }
    all_subscribed = set(event_to_handlers.keys())
    # Entry events: subscribed-to but not published by any handler.
    # Split into "main chain" events (reachable from scrapers) vs "terminal" events
    # (like PipelineCompletedEvent, which is published by CollectionPipeline itself at the
    # very end — no handler publishes it, but it's also not the start of the article chain).
    all_entry = all_subscribed - all_handler_publishes
    # Topology: main-chain entries are entry events whose non-Failed handlers publish further
    # events (i.e., the chain continues). Terminal entries are leaf nodes — handlers that only
    # notify / log and don't publish anything. No string-pattern heuristics needed.
    main_entry = [
        e for e in all_entry
        if any(
            class_publish_map.get(h, [])
            for h in event_to_handlers.get(e, [])
            if "Failed" not in h
        )
    ]
    terminal_entry = [e for e in all_entry if e not in main_entry]

    visited_handlers: set[str] = set()
    ordered_stages: list[dict] = []
    step = 1
    seen_events: set[str] = set(main_entry) | set(terminal_entry)

    # Two-phase BFS: main article chain first, then terminal (PipelineCompletedEvent etc.)
    def _process_queue(initial: list[str]) -> None:
        nonlocal step
        from collections import deque
        queue: deque[str] = deque(initial)
        while queue:
            event = queue.popleft()
            handlers_for_event = event_to_handlers.get(event, [])
            main_handlers = [h for h in handlers_for_event
                             if "Failed" not in h and h not in visited_handlers]
            for hc in main_handlers:
                if hc in visited_handlers:
                    continue
                visited_handlers.add(hc)
                receives = [e for e, hs in event_to_handlers.items() if hc in hs]
                publishes = class_publish_map.get(hc, [])
                success_emits = [e for e in publishes if "Failed" not in e]
                fail_emits = [e for e in publishes if "Failed" in e]
                branches: list[dict] = []
                for fe in fail_emits:
                    for bh in [h for h in event_to_handlers.get(fe, []) if h not in visited_handlers]:
                        visited_handlers.add(bh)
                        branches.append({
                            "label": re.sub(r"([A-Z])", r" \1", fe).strip().replace(" Event", ""),
                            "color": "#e94560",
                            "emits": [fe],
                            "classes": [bh] + handler_related.get(bh, []),
                            "desc": f"{fe} → {bh}",
                        })
                related = handler_related.get(hc, [])
                hc_var = class_to_var.get(hc, "")
                ordered_stages.append({
                    "step": step,
                    "id": re.sub(r"[^a-z]", "", hc.lower()),
                    "icon": _infer_stage_icon(hc),
                    "label": _camel_to_label(hc),
                    "desc": (
                        f"{', '.join(receives)} -> {hc}"
                        + (f" -> {', '.join(success_emits)}" if success_emits else "")
                    ),
                    "color": _STAGE_COLORS[(step - 1) % len(_STAGE_COLORS)],
                    "classes": [hc] + related,
                    "receives": receives,
                    "emits": success_emits,
                    "branches": branches,
                    "di": _build_di_tree(hc_var, var_to_class, var_to_kwargs_vars, class_creates_map),
                })
                step += 1
                for se in success_emits:
                    if se not in seen_events:
                        seen_events.add(se)
                        queue.append(se)

    _process_queue(main_entry)
    _process_queue(terminal_entry)

    # ── 6. Prepend Collection Pipeline stage (entry point) ───────────────────
    _COLLECTION_CLASSES = {"Pipeline", "Scraper", "Executor", "Factory"}
    _COLLECTION_SKIP = {"Handler", "UseCase", "Repository", "Service", "Prompt"}
    collection_classes = [
        cls for cls in dict.fromkeys(var_to_class.values())
        if any(k in cls for k in _COLLECTION_CLASSES)
        and not any(k in cls for k in _COLLECTION_SKIP)
    ]

    for i, s in enumerate(ordered_stages, 2):
        s["step"] = i

    # DI tree for the collection pipeline entry point — prefer the concrete pipeline var
    pipeline_var = next(
        (var for var, cls in var_to_class.items() if cls == "CollectionPipeline"),
        None,
    ) or next(
        (var for var, cls in var_to_class.items() if "Pipeline" in cls and "Stats" not in cls),
        "",
    )
    collection_di = _build_di_tree(pipeline_var, var_to_class, var_to_kwargs_vars, class_creates_map)

    ordered_stages.insert(0, {
        "step": 1,
        "id": "collection",
        "icon": "🚀",
        "label": "Collection Pipeline",
        "desc": (
            "CollectionPipeline.run() 讀取 ScraperSetting，"
            "建立各型 Scraper 執行 discover()，"
            "ScrapeExecutor 並發抓取並 publish ArticleScrapedEvent。"
        ),
        "color": "#BBCC33",
        "classes": collection_classes,
        "receives": [],
        "emits": list(main_entry),
        "branches": [],
        "di": collection_di,
    })

    print(f"Pipeline: generated {len(ordered_stages)} stages")
    return ordered_stages


def build_uml_data() -> dict:
    """Build structured JSON from pyreverse .dot output."""
    classes_dot = OUTPUT_DIR / "classes.dot"

    if not classes_dot.exists():
        print(f"Error: {classes_dot} not found", file=sys.stderr)
        sys.exit(1)

    parsed = parse_dot_file(classes_dot)

    ast_data = build_class_ast_data()
    print(f"AST data extracted for {len(ast_data)} classes")

    for node in parsed["nodes"]:
        node_id = node["id"]
        node["layer"] = classify_layer(node_id)
        node["ca_layer"] = CA_LAYER_MAP.get(node["layer"], "infrastructure")
        node["subgroup"] = classify_subgroup(node_id, node["layer"])
        node["module"] = node_id.rsplit(".", 1)[0] if "." in node_id else ""

        # Use the last segment of the dotted node ID as the class name.
        # Parsing pyreverse's HTML-like DOT labels is fragile (they use << >> HTML strings
        # with spaces that break simple regex parsing); the node ID is always reliable.
        node["class_name"] = node_id.split(".")[-1]
        node["attributes"] = []
        node["methods"] = []
        module_path = node_id.replace(".", "/")
        node["full_path"] = f"src/{module_path}.py"

        # Merge AST data (docstrings, typed signatures)
        ast_info = ast_data.get(node["class_name"], {})
        node["docstring"] = ast_info.get("docstring", "")
        node["typed_attrs"] = ast_info.get("typed_attrs", [])
        node["typed_methods"] = ast_info.get("typed_methods", [])
        node["source_file"] = ast_info.get("source_file", node["full_path"])

        # Context classification uses source_file (full path) first so that
        # src/modules/collection/* and src/modules/intelligence/* are correctly
        # classified even though their pyreverse node IDs strip the modules.* prefix.
        node["context"] = classify_context(node_id, node["source_file"])

    # Collect actual layers found
    found_layers = sorted(set(n["layer"] for n in parsed["nodes"]))
    layer_order = [l for _, l, _ in LAYER_DISPLAY if l in found_layers]
    unknown_count = sum(1 for n in parsed["nodes"] if n["layer"] == "unknown")
    if unknown_count > 0 and "unknown" not in layer_order:
        layer_order.append("unknown")

    # Build Clean Architecture circles summary
    circles = []
    for ca_id, ca_label, ca_color in CA_CIRCLE_META:
        ca_nodes = [n for n in parsed["nodes"] if n["ca_layer"] == ca_id]
        sg_counts: dict[str, int] = {}
        ctx_counts: dict[str, int] = {}
        for n in ca_nodes:
            sg = n["subgroup"]
            sg_counts[sg] = sg_counts.get(sg, 0) + 1
            ctx = n["context"]
            ctx_counts[ctx] = ctx_counts.get(ctx, 0) + 1
        subgroups = [
            {
                "id": sg,
                "label": SUBGROUP_LABELS.get(sg, sg.replace("_", " ").title()),
                "count": cnt,
            }
            for sg, cnt in sorted(sg_counts.items(), key=lambda x: -x[1])
        ]
        context_subgroups = [
            {
                "id": ctx,
                "label": CONTEXT_LABELS.get(ctx, ctx.replace("_", " ").title()),
                "count": cnt,
            }
            for ctx, cnt in sorted(ctx_counts.items(), key=lambda x: -x[1])
        ]
        circles.append({
            "id": ca_id,
            "label": ca_label,
            "color": ca_color,
            "count": len(ca_nodes),
            "subgroups": subgroups,
            "context_subgroups": context_subgroups,
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "layers": layer_order,
        "nodes": parsed["nodes"],
        "edges": parsed["edges"],
        "circles": circles,
        "pipeline": build_pipeline_from_bootstrap(),
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    py_files = collect_py_files()
    print(f"Found {len(py_files)} Python files (excluding tests and __init__)")

    if not run_pyreverse(py_files):
        print("pyreverse failed, aborting", file=sys.stderr)
        sys.exit(1)

    project_name = "ScrapeAnalyzer"
    for suffix in ("classes", "packages"):
        src_dot = OUTPUT_DIR / f"{suffix}_{project_name}.dot"
        dst_dot = OUTPUT_DIR / f"{suffix}.dot"
        if src_dot.exists():
            dst_dot.write_text(src_dot.read_text())
            src_dot.unlink()
            print(f"Renamed {src_dot.name} → {dst_dot.name}")

    # Rewrite classes.dot with layer subgraphs and better layout
    rebuild_dot_with_layers(OUTPUT_DIR / "classes.dot")

    # Build structured JSON
    uml_data = build_uml_data()

    # Print layer distribution
    layer_counts: dict[str, int] = {}
    for n in uml_data["nodes"]:
        layer_counts[n["layer"]] = layer_counts.get(n["layer"], 0) + 1
    print("Layer distribution:")
    for layer in uml_data["layers"]:
        print(f"  {layer}: {layer_counts.get(layer, 0)}")

    json_path = OUTPUT_DIR / "uml-data.json"
    json_path.write_text(json.dumps(uml_data, indent=2, ensure_ascii=False))
    print(f"Written {json_path} ({len(uml_data['nodes'])} nodes, {len(uml_data['edges'])} edges)")


if __name__ == "__main__":
    main()
