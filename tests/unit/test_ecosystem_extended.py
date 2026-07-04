from pathlib import Path

from converge.models import EntityType
from converge.scanner.ecosystem import (
    scan_apt_txt,
    scan_cargo_toml,
    scan_environment_yml,
)


def test_scan_apt_txt(tmp_path: Path) -> None:
    (tmp_path / "apt.txt").write_text("libpq-dev\nbuild-essential\n", encoding="utf-8")
    entities, rels = scan_apt_txt(tmp_path)
    assert len(entities) == 2
    assert all(e.type == EntityType.SYSTEM_PACKAGE for e in entities)
    assert len(rels) == 2


def test_scan_cargo_toml(tmp_path: Path) -> None:
    (tmp_path / "Cargo.toml").write_text(
        "[dependencies]\nserde = \"1\"\n",
        encoding="utf-8",
    )
    entities, rels = scan_cargo_toml(tmp_path)
    assert any(e.type == EntityType.CARGO_CRATE and e.name == "serde" for e in entities)
    assert rels


def test_scan_environment_yml(tmp_path: Path) -> None:
    (tmp_path / "environment.yml").write_text(
        "name: demo\ndependencies:\n  - python=3.12\n  - numpy=1.26\n",
        encoding="utf-8",
    )
    entities, rels = scan_environment_yml(tmp_path)
    assert any(e.type == EntityType.CONDA_PACKAGE and e.name == "numpy" for e in entities)
    assert rels
