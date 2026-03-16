from pathlib import Path

from converge.scanner.ast_parser import PythonASTParser


def test_ast_parser_ignores_internal_src_package(tmp_path: Path) -> None:
    src_pkg = tmp_path / "src" / "myapp"
    src_pkg.mkdir(parents=True)
    (src_pkg / "__init__.py").write_text("")
    (src_pkg / "service.py").write_text("import requests\nfrom myapp import helpers\n")
    (src_pkg / "helpers.py").write_text("")

    parser = PythonASTParser(str(tmp_path))
    _modules, relationships = parser.scan_directory()

    assert any(rel.target_id == "pkg:requests" for rel in relationships)
    assert not any(rel.target_id == "pkg:myapp" for rel in relationships)
