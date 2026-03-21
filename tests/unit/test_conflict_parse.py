from converge.cli.conflict_parse import parse_conflict_id


def test_parse_unresolved() -> None:
    cid = "conflict:unresolved_mod:main.py_pkg:requests"
    p = parse_conflict_id(cid)
    assert p["kind"] == "unresolved_import"
    assert p["module"] == "mod:main.py"
    assert p["package_name"] == "requests"


def test_parse_unused() -> None:
    p = parse_conflict_id("conflict:unused_pkg:httpx")
    assert p["kind"] == "unused_dependency"
    assert p["package_ref"] == "pkg:httpx"


def test_parse_clash() -> None:
    p = parse_conflict_id("conflict:clash_pkg:a_pkg:b")
    assert p["kind"] == "version_clash"


def test_parse_invalid() -> None:
    p = parse_conflict_id("not-a-conflict")
    assert p["kind"] == "invalid"
