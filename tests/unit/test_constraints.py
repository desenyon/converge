from converge.versioning.constraints import (
    constraints_conflict,
    parse_requirement,
    version_satisfies,
)


def test_parse_requirement_pep508() -> None:
    name, spec = parse_requirement("requests>=2.28,<3")
    assert name == "requests"
    assert spec is not None
    assert "2.28" in spec


def test_version_satisfies_pin() -> None:
    assert version_satisfies("2.32.0", "==2.32.0")
    assert not version_satisfies("2.31.0", "==2.32.0")


def test_constraints_conflict_disjoint() -> None:
    assert constraints_conflict("==1.0", "==2.0")
    assert not constraints_conflict(">=1.0", "==2.0")
