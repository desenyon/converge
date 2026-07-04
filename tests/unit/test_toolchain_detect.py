from pathlib import Path

from converge.toolchain.detect import detect_toolchain


def test_detect_uv_from_lock(tmp_path: Path) -> None:
    (tmp_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    assert detect_toolchain(tmp_path) == "uv"


def test_detect_pip_tools_from_in_file(tmp_path: Path) -> None:
    (tmp_path / "requirements.in").write_text("requests\n", encoding="utf-8")
    assert detect_toolchain(tmp_path) == "pip-tools"


def test_detect_pip_default(tmp_path: Path) -> None:
    assert detect_toolchain(tmp_path) == "pip"
