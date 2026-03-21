from pathlib import Path

from converge.lockfile import summarize_lockfiles


def test_uv_lock_parses_package_table(tmp_path: Path) -> None:
    (tmp_path / "uv.lock").write_text(
        """version = 1
[[package]]
name = "requests"
version = "2.32.0"
""",
        encoding="utf-8",
    )
    data = summarize_lockfiles(tmp_path)
    uv = next(x for x in data["lockfiles"] if x["kind"] == "uv")
    assert any(p["name"] == "requests" for p in uv.get("resolved_packages", []))
