from pathlib import Path

from converge.scanner.ast_parser import PythonASTParser
from converge.settings import ConvergeSettings


def test___import___detected(tmp_path: Path) -> None:
    (tmp_path / "d.py").write_text("x = __import__('requests')\n", encoding="utf-8")
    p = PythonASTParser(str(tmp_path), settings=ConvergeSettings())
    _m, rels = p.scan_files([tmp_path / "d.py"])
    assert any(r.target_id == "pkg:requests" for r in rels)
    assert any(r.metadata.get("dynamic") == "__import__" for r in rels)


def test_importlib_import_module_detected(tmp_path: Path) -> None:
    (tmp_path / "d.py").write_text(
        "import importlib\nm = importlib.import_module('httpx')\n", encoding="utf-8"
    )
    p = PythonASTParser(str(tmp_path), settings=ConvergeSettings())
    _m, rels = p.scan_files([tmp_path / "d.py"])
    assert any(r.target_id == "pkg:httpx" for r in rels)
