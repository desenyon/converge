from pathlib import Path

from converge.scanner.ast_parser import PythonASTParser
from converge.settings import ConvergeSettings


def test_type_checking_imports_skipped_by_default(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text(
        """from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import requests
x = 1
""",
        encoding="utf-8",
    )
    s = ConvergeSettings(skip_type_checking_imports=True)
    p = PythonASTParser(str(tmp_path), settings=s)
    mods, rels = p.scan_files([tmp_path / "m.py"])
    assert len(mods) == 1
    assert not any("requests" in r.target_id for r in rels)


def test_type_checking_imports_included_when_disabled(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text(
        """from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import requests
""",
        encoding="utf-8",
    )
    s = ConvergeSettings(skip_type_checking_imports=False)
    p = PythonASTParser(str(tmp_path), settings=s)
    _mods, rels = p.scan_files([tmp_path / "m.py"])
    assert any(r.target_id == "pkg:requests" for r in rels)
