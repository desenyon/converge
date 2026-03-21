from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectContext:
    root_dir: Path
    artifact_dir: Path
    graph_db_path: Path
    default_env_path: Path
    export_dir: Path
    audit_log_path: Path
    scan_state_path: Path

    @classmethod
    def from_target(cls, target: Path | str) -> ProjectContext:
        root_dir = Path(target).resolve()
        artifact_dir = root_dir / ".converge"
        return cls(
            root_dir=root_dir,
            artifact_dir=artifact_dir,
            graph_db_path=artifact_dir / "graph.db",
            default_env_path=root_dir / ".venv",
            export_dir=artifact_dir / "exports",
            audit_log_path=artifact_dir / "audit.log",
            scan_state_path=artifact_dir / "scan_state.json",
        )
