"""Generate a database schema diagram from models/*.py via static AST analysis.

Does NOT import models/ (no SQLAlchemy/pgvector/etc. dependency needed in the
docs-build job — see specs/016-db-schema-brushup/research.md §5). Parses each
model file's source text directly, the same static-analysis philosophy as
scripts/generate_uml.py's pyreverse-based approach for src/.

Output:
  - site/public/guide/architecture/db-schema.dot  (Graphviz DOT, rendered
    client-side by @viz-js/viz — same pattern as classes.dot/viewer.html)
"""
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = REPO_ROOT / "models"
OUTPUT_DIR = REPO_ROOT / "site" / "public" / "guide" / "architecture"

EXCLUDED_FILES = {"__init__.py", "base.py", "types.py", "db_schema.py"}

# Display order + color per schema, for subgraph clusters.
SCHEMA_DISPLAY = [
    ("core", "#77AADD"),
    ("collection", "#BBCC33"),
    ("intelligence", "#EEDD88"),
    ("ai_infra", "#EE8866"),
    ("user_prefs", "#99DDFF"),
    ("auth", "#CCCCCC"),
    ("vectors", "#DDDDDD"),
]


@dataclass
class ColumnInfo:
    name: str
    type_repr: str
    nullable: bool
    is_primary_key: bool
    is_indexed: bool = False


@dataclass
class ForeignKeyInfo:
    column: str
    target_schema: str
    target_table: str
    target_column: str


@dataclass
class TableInfo:
    name: str
    schema: str
    model_class: str
    source_file: str
    columns: list = field(default_factory=list)
    foreign_keys: list = field(default_factory=list)


class ModelParseError(Exception):
    pass


def _load_db_schema_enum() -> dict:
    """Parse models/db_schema.py's `MEMBER = "value"` assignments inside the
    DbSchema class body, without importing it."""
    path = MODELS_DIR / "db_schema.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    members = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "DbSchema":
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            members[target.id] = stmt.value.value
    if not members:
        raise ModelParseError(f"Could not parse any DbSchema members from {path}")
    return members


def _resolve_schema_value(node: ast.AST, enum_members: dict, source_file: str) -> str:
    """Resolve a __table_args__ schema value: either a string literal, or a
    `DbSchema.<MEMBER>` / `DbSchema.<MEMBER>.value` attribute chain."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value

    # DbSchema.<MEMBER>.value  -> Attribute(value=Attribute(value=Name('DbSchema'), attr=MEMBER), attr='value')
    # DbSchema.<MEMBER>        -> Attribute(value=Name('DbSchema'), attr=MEMBER)
    target = node
    if isinstance(target, ast.Attribute) and target.attr == "value":
        target = target.value
    if (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "DbSchema"
        and target.attr in enum_members
    ):
        return enum_members[target.attr]

    raise ModelParseError(
        f"{source_file}: unrecognized __table_args__ schema expression: {ast.dump(node)}"
    )


def _extract_schema_from_table_args(table_args: ast.AST, enum_members: dict, source_file: str) -> str:
    """table_args is either a Dict literal, or a Tuple whose last element is a Dict."""
    if isinstance(table_args, ast.Dict):
        target_dict = table_args
    elif isinstance(table_args, ast.Tuple) and table_args.elts and isinstance(table_args.elts[-1], ast.Dict):
        target_dict = table_args.elts[-1]
    else:
        raise ModelParseError(f"{source_file}: unrecognized __table_args__ shape: {ast.dump(table_args)}")

    for key, value in zip(target_dict.keys, target_dict.values):
        if isinstance(key, ast.Constant) and key.value == "schema":
            return _resolve_schema_value(value, enum_members, source_file)

    raise ModelParseError(f"{source_file}: __table_args__ dict has no 'schema' key")


def _extract_indexed_columns(table_args: ast.AST) -> set[str]:
    """Column names covered by an `Index('name', 'col1', 'col2', ...)` entry
    in a tuple-form __table_args__ (single-column and composite alike)."""
    if not isinstance(table_args, ast.Tuple):
        return set()

    indexed: set[str] = set()
    for elt in table_args.elts:
        if isinstance(elt, ast.Call) and isinstance(elt.func, ast.Name) and elt.func.id == "Index":
            for arg in elt.args[1:]:  # args[0] is the index name
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    indexed.add(arg.value)
    return indexed


def _sanitize_port(name: str) -> str:
    return "".join(c if c.isalnum() or c == "_" else "_" for c in name)


def _cell_sig(schema: str, table: str, column: str) -> str:
    """Unique id (safe for both a Graphviz `id=` and a DOM lookup) for one
    column's cells — the frontend hover handler uses this to find the two
    ends of an FK relationship and highlight them."""
    return f"cell_{_sanitize_port(schema)}_{_sanitize_port(table)}_{_sanitize_port(column)}"


def _table_sig(schema: str, table: str) -> str:
    return f"tbl_{_sanitize_port(schema)}_{_sanitize_port(table)}"


def _type_repr(annotation_node: ast.AST) -> str:
    try:
        return ast.unparse(annotation_node)
    except Exception:
        return "?"


def _extract_foreign_key(call: ast.Call, source_file: str) -> ForeignKeyInfo | None:
    for arg in call.args:
        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == "ForeignKey":
            if not arg.args or not isinstance(arg.args[0], ast.Constant):
                continue
            target = arg.args[0].value
            parts = target.split(".")
            if len(parts) == 3:
                schema, table, column = parts
            elif len(parts) == 2:
                schema, table, column = "public", parts[0], parts[1]
            else:
                raise ModelParseError(f"{source_file}: unparseable ForeignKey target '{target}'")
            return ForeignKeyInfo(column="", target_schema=schema, target_table=table, target_column=column)
    return None


def _column_name_from_target(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _parse_columns_and_fks(class_or_call_body, source_file: str, table_name: str, indexed_columns: set | None = None):
    columns: list[ColumnInfo] = []
    fks: list[ForeignKeyInfo] = []
    indexed_columns = indexed_columns or set()

    def handle_column_call(col_name: str, call: ast.Call):
        # Column('db_col_name', Type, ...) overrides the DB column name via a
        # leading string literal (e.g. Article.metadata_ = Column('metadata', JSONB)) —
        # skip it so the type isn't misread as the literal name.
        type_args = call.args[1:] if call.args and isinstance(call.args[0], ast.Constant) else call.args
        type_repr = _type_repr(type_args[0]) if type_args else "?"
        nullable = True
        is_pk = False
        for kw in call.keywords:
            if kw.arg == "nullable" and isinstance(kw.value, ast.Constant):
                nullable = bool(kw.value.value)
            if kw.arg == "primary_key" and isinstance(kw.value, ast.Constant):
                is_pk = bool(kw.value.value)
        columns.append(ColumnInfo(
            name=col_name, type_repr=type_repr, nullable=nullable, is_primary_key=is_pk,
            is_indexed=col_name in indexed_columns,
        ))

        fk = _extract_foreign_key(call, source_file)
        if fk is not None:
            fk.column = col_name
            fks.append(fk)

    for stmt in class_or_call_body:
        # class body: `col = Column(...)`
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            func_name = call.func.id if isinstance(call.func, ast.Name) else None
            if func_name == "Column" and len(stmt.targets) == 1:
                col_name = _column_name_from_target(stmt.targets[0])
                if col_name:
                    handle_column_call(col_name, call)

    return columns, fks


def parse_model_file(path: Path, enum_members: dict) -> list[TableInfo]:
    try:
        source_file = str(path.relative_to(REPO_ROOT))
    except ValueError:
        source_file = str(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=source_file)
    tables: list[TableInfo] = []

    for node in ast.iter_child_nodes(tree):
        # module-level association Table(...) calls, e.g. models/tag.py's article_tags
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Name) and call.func.id == "Table":
                if not call.args or not isinstance(call.args[0], ast.Constant):
                    continue
                table_name = call.args[0].value
                schema = "public"
                for kw in call.keywords:
                    if kw.arg == "schema":
                        schema = _resolve_schema_value(kw.value, enum_members, source_file)
                # Table() columns are positional Column(...) call args, not assignments — parse directly.
                columns = []
                fks = []
                for arg in call.args[1:]:
                    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == "Column":
                        if not arg.args or not isinstance(arg.args[0], ast.Constant):
                            continue
                        col_name = arg.args[0].value
                        type_repr = _type_repr(arg.args[1]) if len(arg.args) > 1 else "?"
                        is_pk = any(
                            kw.arg == "primary_key" and isinstance(kw.value, ast.Constant) and kw.value.value
                            for kw in arg.keywords
                        )
                        columns.append(ColumnInfo(name=col_name, type_repr=type_repr, nullable=True, is_primary_key=is_pk))
                        fk = _extract_foreign_key(arg, source_file)
                        if fk is not None:
                            fk.column = col_name
                            fks.append(fk)
                tables.append(TableInfo(
                    name=table_name, schema=schema, model_class="(association table)",
                    source_file=source_file, columns=columns, foreign_keys=fks,
                ))

        if not isinstance(node, ast.ClassDef):
            continue
        base_names = [b.id for b in node.bases if isinstance(b, ast.Name)]
        if "Base" not in base_names:
            continue

        tablename = None
        schema = "public"
        indexed_columns: set[str] = set()
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                if stmt.targets[0].id == "__tablename__" and isinstance(stmt.value, ast.Constant):
                    tablename = stmt.value.value
                if stmt.targets[0].id == "__table_args__":
                    schema = _extract_schema_from_table_args(stmt.value, enum_members, source_file)
                    indexed_columns = _extract_indexed_columns(stmt.value)

        if tablename is None:
            continue  # not every Base subclass necessarily maps a table in a way we care about

        columns, fks = _parse_columns_and_fks(node.body, source_file, tablename, indexed_columns)
        tables.append(TableInfo(
            name=tablename, schema=schema, model_class=node.name,
            source_file=source_file, columns=columns, foreign_keys=fks,
        ))

    return tables


def collect_all_tables() -> list[TableInfo]:
    enum_members = _load_db_schema_enum()
    tables: list[TableInfo] = []
    for path in sorted(MODELS_DIR.glob("*.py")):
        if path.name in EXCLUDED_FILES:
            continue
        tables.extend(parse_model_file(path, enum_members))
    return tables


def render_dot(tables: list[TableInfo]) -> str:
    by_schema: dict[str, list[TableInfo]] = {}
    for t in tables:
        by_schema.setdefault(t.schema, []).append(t)

    lines = [
        "digraph db_schema {",
        '  rankdir="LR";',
        '  nodesep="0.6";',
        '  ranksep="1.0";',
        '  node [shape=plaintext, fontname="Helvetica"];',
        '  edge [fontname="Helvetica", fontsize=10];',
        "",
    ]

    schema_order = [s for s, _ in SCHEMA_DISPLAY if s in by_schema]
    schema_order += sorted(s for s in by_schema if s not in schema_order)
    color_map = dict(SCHEMA_DISPLAY)
    schema_rank = {s: i for i, s in enumerate(schema_order)}

    node_id = lambda schema, name: f'"{schema}.{name}"'  # noqa: E731

    # (schema, table) -> {column names}, so FK edges can target the exact row
    # of the referenced key instead of just the table node when the target
    # column was itself discovered from a parsed model.
    columns_by_table: dict[tuple[str, str], set[str]] = {
        (t.schema, t.name): {c.name for c in t.columns} for t in tables
    }

    for schema in schema_order:
        color = color_map.get(schema, "#EEEEEE")
        lines.append(f'  subgraph "cluster_{schema}" {{')
        lines.append(f'    label="{schema}"; style=filled; color="{color}"; fontname="Helvetica"; fontsize=14;')
        for t in sorted(by_schema[schema], key=lambda t: t.name):
            fk_columns = {fk.column for fk in t.foreign_keys}
            rows = []
            for c in t.columns:
                markers = []
                if c.is_primary_key:
                    markers.append("PK")
                if c.name in fk_columns:
                    markers.append("FK")
                if c.is_indexed:
                    markers.append("IDX")
                # Graphviz's HTML-like label grammar rejects an empty <b></b> —
                # a single bad node aborts parsing of the whole label, so leave
                # the marker cell bare (no nested tags) when there's nothing to show.
                marker_text = " ".join(markers)
                marker_cell = f'<font point-size="9"><b>{marker_text}</b></font>' if marker_text else ""
                # Two ports per row, one on the leftmost cell and one on the
                # rightmost cell — not the middle "name" column — so a `:w`/`:e`
                # compass edge lands on the table's actual left/right border for
                # that row instead of an internal column boundary it would have
                # to cross the row to reach.
                port = _sanitize_port(c.name)
                # `id=` on each cell is inert for Graphviz itself but is carried
                # straight through to the rendered SVG's `id` attribute — the
                # frontend hover handler (DbSchemaViewer.vue) uses these to find
                # and highlight the exact column cells an FK edge connects.
                sig = _cell_sig(schema, t.name, c.name)
                rows.append(
                    f'<tr>'
                    f'<td align="center" id="{sig}_l" port="{port}_l">{marker_cell}</td>'
                    f'<td align="left" id="{sig}_m">{c.name}</td>'
                    f'<td align="left" id="{sig}_r" port="{port}_r"><font point-size="10">{c.type_repr}</font></td>'
                    f'</tr>'
                )
            label = (
                f'<<table border="1" cellborder="1" cellspacing="0" bgcolor="white">'
                f'<tr><td colspan="3" bgcolor="#333333"><font color="white"><b>{t.name}</b></font></td></tr>'
                f"{''.join(rows)}"
                f"</table>>"
            )
            lines.append(f'    {node_id(schema, t.name)} [id="{_table_sig(schema, t.name)}", label={label}];')
        lines.append("  }")
        lines.append("")

    for t in tables:
        for fk in t.foreign_keys:
            # With rankdir=LR, clusters are laid out left-to-right in schema_order.
            # Pinning the edge to the west/east compass point of its row (rather
            # than letting Graphviz pick automatically) keeps the line hugging the
            # table's left/right border for that row instead of cutting across the
            # table's interior to reach a port on a row it isn't level with.
            going_rightward = schema_rank.get(fk.target_schema, 0) >= schema_rank.get(t.schema, 0)
            tail_side, head_side = ("e", "w") if going_rightward else ("w", "e")
            side_suffix = {"e": "r", "w": "l"}

            src = f"{node_id(t.schema, t.name)}:{_sanitize_port(fk.column)}_{side_suffix[tail_side]}:{tail_side}"
            target_key = (fk.target_schema, fk.target_table)
            target_resolved = fk.target_column in columns_by_table.get(target_key, set())
            if target_resolved:
                dst = (
                    f"{node_id(fk.target_schema, fk.target_table)}"
                    f":{_sanitize_port(fk.target_column)}_{side_suffix[head_side]}:{head_side}"
                )
            else:
                dst = f"{node_id(fk.target_schema, fk.target_table)}:{head_side}"

            src_sig = _cell_sig(t.schema, t.name, fk.column)
            dst_sig = (
                _cell_sig(fk.target_schema, fk.target_table, fk.target_column)
                if target_resolved
                else _table_sig(fk.target_schema, fk.target_table)
            )
            tooltip = (
                f"{t.schema}.{t.name}.{fk.column} → "
                f"{fk.target_schema}.{fk.target_table}.{fk.target_column}"
            )

            cross_schema = fk.target_schema != t.schema
            style = 'color="#e94560", penwidth=1.5' if cross_schema else 'color="#888888"'
            lines.append(
                f'  {src} -> {dst} [id="fkedge--{src_sig}--{dst_sig}", tooltip="{tooltip}", '
                f'{style}, label="{fk.column}"];'
            )

    lines.append("}")
    return "\n".join(lines)


def main() -> None:
    try:
        tables = collect_all_tables()
    except ModelParseError as e:
        print(f"ERROR: failed to parse models for DB schema diagram: {e}", file=sys.stderr)
        sys.exit(1)

    if not tables:
        print("ERROR: no tables discovered under models/ — refusing to write an empty diagram", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dot_source = render_dot(tables)
    dot_path = OUTPUT_DIR / "db-schema.dot"
    dot_path.write_text(dot_source, encoding="utf-8")

    by_schema_count: dict[str, int] = {}
    for t in tables:
        by_schema_count[t.schema] = by_schema_count.get(t.schema, 0) + 1
    print(f"Discovered {len(tables)} tables across {len(by_schema_count)} schemas:")
    for schema, count in sorted(by_schema_count.items()):
        print(f"  {schema}: {count}")
    print(f"Written {dot_path}")


if __name__ == "__main__":
    main()
