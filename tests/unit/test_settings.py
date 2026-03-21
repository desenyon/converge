from pathlib import Path

from converge.settings import ConvergeSettings, load_converge_settings


def test_load_converge_settings_from_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "x"
[tool.converge]
incremental_scan = true
test_roots = ["tests", "integration"]
repair_targets = ["pyproject", "requirements"]
"""
    )
    s = load_converge_settings(tmp_path)
    assert s.incremental_scan is True
    assert s.test_roots == ("tests", "integration")
    assert s.repair_targets == ("pyproject", "requirements")


def test_dotfile_merged_under_pyproject(tmp_path: Path) -> None:
    (tmp_path / ".converge.toml").write_text(
        """
incremental_scan = true
scan_workers = 2
"""
    )
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "x"
[tool.converge]
incremental_scan = false
"""
    )
    s = load_converge_settings(tmp_path)
    assert s.incremental_scan is False
    assert s.scan_workers == 2


def test_converge_settings_defaults() -> None:
    s = ConvergeSettings()
    assert s.skip_type_checking_imports is True
    assert "pyproject" in s.repair_targets
