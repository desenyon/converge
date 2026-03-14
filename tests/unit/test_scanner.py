from pathlib import Path

from converge.scanner.ast_parser import PythonASTParser
from converge.scanner.project import ProjectParser


def test_project_parser(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
    [project]
    name = "test_repo"
    dependencies = ["pytest>=8.0"]
    """)

    parser = ProjectParser(str(tmp_path))
    pkgs, rels = parser.parse_pyproject()

    assert len(pkgs) == 1
    assert pkgs[0].name == "pytest"
    assert len(rels) == 1
    assert rels[0].source_id == "repo:" + tmp_path.name
    assert rels[0].target_id == "pkg:pytest"


def test_ast_parser(tmp_path: Path) -> None:
    src_file = tmp_path / "main.py"
    src_file.write_text("""
import fastapi
from pydantic import BaseModel
    """)

    parser = PythonASTParser(str(tmp_path))
    mods, rels = parser.scan_directory()

    assert len(mods) == 1
    assert mods[0].name == "main.py"

    # fastapi import
    assert any(r.target_id == "pkg:fastapi" for r in rels)
    # pydantic import
    assert any(r.target_id == "pkg:pydantic" for r in rels)
