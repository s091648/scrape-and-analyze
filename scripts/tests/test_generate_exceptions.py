import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import scripts.generate_exceptions as gen  # noqa: E402
from scripts.generate_exceptions import (  # noqa: E402
    ExceptionCatalogParseError,
    generate,
)


def _write(base: Path, rel_path: str, content: str) -> Path:
    path = base / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def scan_root(tmp_path, monkeypatch):
    monkeypatch.setattr(gen, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gen, "SCAN_DIRS", ["src"])
    return tmp_path


def _by_name(result, name):
    return next(e for e in result["exceptions"] if e["name"] == name)


def test_custom_exception_class_detected(scan_root):
    """A class only appears in the catalog if it's actually raised somewhere
    (spec.md Key Entity: "every distinct exception class raised somewhere")."""
    _write(scan_root, "src/errors.py", '''
class RateLimitExhausted(Exception):
    """Raised when a provider's daily quota is exhausted."""
    pass

def check_quota():
    raise RateLimitExhausted("quota exceeded")
''')
    result = generate()
    exc = _by_name(result, "RateLimitExhausted")
    assert exc["category"] == "custom"
    assert exc["bases"] == ["Exception"]
    assert exc["docstring"] == "Raised when a provider's daily quota is exhausted."
    assert exc["defined_at"]["file"] == "src/errors.py"


def test_defined_but_never_raised_class_excluded(scan_root):
    _write(scan_root, "src/errors.py", '''
class NeverRaised(Exception):
    pass
''')
    result = generate()
    assert result["exceptions"] == []


def test_indirect_custom_subclass_resolved_via_chain(scan_root):
    _write(scan_root, "src/errors.py", '''
class BaseAppError(Exception):
    pass

class SpecificError(BaseAppError):
    pass

def do_thing():
    raise SpecificError("boom")
''')
    result = generate()
    assert _by_name(result, "SpecificError")["category"] == "custom"


def test_raise_call_resolved(scan_root):
    _write(scan_root, "src/mod.py", '''
def do_thing():
    raise ValueError("bad input")
''')
    result = generate()
    exc = _by_name(result, "ValueError")
    assert exc["category"] == "builtin"
    assert len(exc["raise_sites"]) == 1
    site = exc["raise_sites"][0]
    assert site["file"] == "src/mod.py"
    assert site["function"] == "do_thing"
    assert "raise ValueError" in site["snippet"]


def test_raise_from_resolved(scan_root):
    _write(scan_root, "src/mod.py", '''
def do_thing():
    try:
        pass
    except OSError as e:
        raise RuntimeError("wrapped") from e
''')
    result = generate()
    exc = _by_name(result, "RuntimeError")
    assert len(exc["raise_sites"]) == 1


def test_bare_reraise_resolved_via_except_handler(scan_root):
    _write(scan_root, "src/mod.py", '''
def do_thing():
    try:
        pass
    except ValueError:
        raise
''')
    result = generate()
    exc = _by_name(result, "ValueError")
    assert len(exc["raise_sites"]) == 1


def test_raise_e_reraise_resolved_via_except_handler(scan_root):
    _write(scan_root, "src/mod.py", '''
def do_thing():
    try:
        pass
    except ValueError as e:
        raise e
''')
    result = generate()
    exc = _by_name(result, "ValueError")
    assert len(exc["raise_sites"]) == 1


def test_unresolvable_reraise_excluded_bare_except(scan_root):
    """A bare `except:` (no type) can't resolve a re-raise inside it."""
    _write(scan_root, "src/mod.py", '''
def do_thing():
    try:
        pass
    except:
        raise
''')
    result = generate()
    assert result["exceptions"] == []


def test_unresolvable_reraise_excluded_multi_type_except(scan_root):
    _write(scan_root, "src/mod.py", '''
def do_thing():
    try:
        pass
    except (ValueError, TypeError):
        raise
''')
    result = generate()
    assert result["exceptions"] == []


def test_http_exception_status_code_extracted(scan_root):
    _write(scan_root, "src/routers.py", '''
from fastapi import HTTPException

def handler():
    raise HTTPException(status_code=404, detail="not found")
''')
    result = generate()
    exc = _by_name(result, "HTTPException")
    assert exc["category"] == "framework"
    assert exc["raise_sites"][0]["status_code"] == 404


def test_http_exception_without_literal_status_code_has_none(scan_root):
    _write(scan_root, "src/routers.py", '''
from fastapi import HTTPException

def handler(code):
    raise HTTPException(status_code=code, detail="dynamic")
''')
    result = generate()
    exc = _by_name(result, "HTTPException")
    assert exc["raise_sites"][0]["status_code"] is None


def test_tests_directory_excluded(scan_root):
    _write(scan_root, "src/tests/test_mod.py", '''
def test_foo():
    raise AssertionError("should not appear")
''')
    result = generate()
    assert result["exceptions"] == []


def test_unparseable_file_raises(scan_root):
    _write(scan_root, "src/broken.py", "def broken(:\n    pass")
    with pytest.raises(ExceptionCatalogParseError):
        generate()


def test_raise_bare_class_name_without_parens_resolved(scan_root):
    _write(scan_root, "src/mod.py", '''
def do_thing():
    raise ValueError
''')
    result = generate()
    assert len(_by_name(result, "ValueError")["raise_sites"]) == 1


def test_raise_lowercase_variable_not_the_except_binding_excluded(scan_root):
    """`raise last_403_exc` — a stored exception instance under a name other than the
    except binding — can't be resolved via static analysis and must not be
    misattributed to a fake exception type literally named `last_403_exc`."""
    _write(scan_root, "src/mod.py", '''
def do_thing(items):
    last_403_exc = None
    for item in items:
        try:
            pass
        except PermissionError as exc:
            last_403_exc = exc
            continue
    raise last_403_exc
''')
    result = generate()
    assert result["exceptions"] == []


def test_enclosing_function_qualified_for_method(scan_root):
    _write(scan_root, "src/mod.py", '''
class Service:
    def process(self):
        raise ValueError("bad")
''')
    result = generate()
    exc = _by_name(result, "ValueError")
    assert exc["raise_sites"][0]["function"] == "Service.process"
