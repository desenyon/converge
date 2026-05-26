import tomllib
from pathlib import Path

from converge.cli.jsonutil import envelope
from converge.version_info import JSON_SCHEMA_VERSION, package_version


def test_envelope_adds_versions() -> None:
    out = envelope({"command": "test", "ok": True})
    assert out["schema_version"] == JSON_SCHEMA_VERSION
    assert out["tool_version"] == package_version()
    assert out["ok"] is True


def test_package_version_matches_source_pyproject() -> None:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with pyproject_path.open("rb") as handle:
        expected = tomllib.load(handle)["project"]["version"]

    assert package_version() == expected
