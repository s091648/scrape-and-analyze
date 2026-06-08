"""Generate UML class diagram data from src/ using pyreverse.

Outputs:
  - site/guide/architecture/classes.dot  (raw Graphviz dot)
  - site/guide/architecture/packages.dot  (package-level dot)
  - site/guide/architecture/uml-data.json (structured data for Vue components)
"""

import json
import re
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
OUTPUT_DIR = REPO_ROOT / "site" / "guide" / "architecture"

# Layer classification based on pyreverse node ID prefixes.
# pyreverse strips the src.modules.xxx prefix, so we match on what it actually outputs.
LAYER_RULES = [
    # Domain layer (from both modules and shared)
    (r"^(domain\.(entities|repositories|value_objects|services|factories|events))\.", "domain"),
    (r"^(entities\.|repositories\.|value_objects\.)", "domain"),
    # Application layer (from modules)
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


def classify_layer(node_id: str) -> str:
    for pattern, layer in LAYER_RULES:
        if re.search(pattern, node_id):
            return layer
    return "unknown"


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

    cmd = [
        "pyreverse",
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


def build_uml_data() -> dict:
    """Build structured JSON from pyreverse .dot output."""
    classes_dot = OUTPUT_DIR / "classes.dot"

    if not classes_dot.exists():
        print(f"Error: {classes_dot} not found", file=sys.stderr)
        sys.exit(1)

    parsed = parse_dot_file(classes_dot)

    for node in parsed["nodes"]:
        node_id = node["id"]
        node["layer"] = classify_layer(node_id)
        node["module"] = node_id.rsplit(".", 1)[0] if "." in node_id else ""

        label = node.get("label", "")
        parsed_label = _parse_label(label)
        node["class_name"] = parsed_label["class_name"] or node_id.split(".")[-1]
        node["attributes"] = parsed_label["attributes"]
        node["methods"] = parsed_label["methods"]

        module_path = node_id.replace(".", "/")
        node["full_path"] = f"src/{module_path}.py"

    # Collect actual layers found
    found_layers = sorted(set(n["layer"] for n in parsed["nodes"]))
    layer_order = [l for _, l, _ in LAYER_DISPLAY if l in found_layers]
    unknown_count = sum(1 for n in parsed["nodes"] if n["layer"] == "unknown")
    if unknown_count > 0 and "unknown" not in layer_order:
        layer_order.append("unknown")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "layers": layer_order,
        "nodes": parsed["nodes"],
        "edges": parsed["edges"],
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
