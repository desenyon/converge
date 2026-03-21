from pathlib import Path

from converge.scanner.incremental import fingerprint_files, is_tree_unchanged, write_scan_state


def test_incremental_short_circuit_when_hashes_match(tmp_path: Path) -> None:
    a = tmp_path / "a.py"
    a.write_text("x = 1\n", encoding="utf-8")
    state = tmp_path / "state.json"
    write_scan_state(state, tmp_path, [a])
    assert is_tree_unchanged(state, tmp_path, [a]) is True


def test_incremental_runs_when_file_changes(tmp_path: Path) -> None:
    a = tmp_path / "a.py"
    a.write_text("x = 1\n", encoding="utf-8")
    state = tmp_path / "state.json"
    write_scan_state(state, tmp_path, [a])
    a.write_text("x = 2\n", encoding="utf-8")
    assert is_tree_unchanged(state, tmp_path, [a]) is False


def test_fingerprint_files_skips_unrelated(tmp_path: Path) -> None:
    fp = fingerprint_files(tmp_path, [])
    assert fp == {}
