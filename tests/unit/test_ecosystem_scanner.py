from pathlib import Path

from converge.models import EntityType
from converge.scanner.ecosystem import scan_dockerfile_system_packages, scan_package_json


def test_scan_package_json(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"react": "^18.0.0"}, "devDependencies": {"eslint": "^8.0.0"}}',
        encoding="utf-8",
    )
    entities, rels = scan_package_json(tmp_path)
    assert len(entities) == 2
    assert any(e.type == EntityType.NPM_PACKAGE and e.name == "react" for e in entities)
    assert len(rels) == 2


def test_scan_dockerfile_apt_packages(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text(
        "FROM ubuntu\nRUN apt-get install -y curl libpq-dev\n",
        encoding="utf-8",
    )
    entities, _rels = scan_dockerfile_system_packages(tmp_path)
    names = {e.name for e in entities}
    assert "curl" in names
    assert "libpq-dev" in names
