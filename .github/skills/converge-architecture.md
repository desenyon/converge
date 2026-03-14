---
description: Guide for agents working on the Converge architecture, covering the graph schema, scanner, solver, and validation loops.
---

# Converge Architecture Guide for Agents

Converge is a Python-first environment convergence platform.

## 1. Graph Schema
The graph is backed by SQLite via `SQLModel` but loaded fully into `networkx.DiGraph` for traversals.
- **Entities**: Found in `src/converge/models.py` (`Repository`, `Package`, `Environment`, `Module`, `Route`, `ExternalAPI`, `PythonVersion`).
- **Relationships**: `IMPORTS`, `REQUIRES`, `CONFLICTS_WITH`, `EXPOSES`, etc.
- **ID Format**: IDs usually prefix the type, e.g., `repo:name`, `pkg:name`, `mod:src/app.py`.

## 2. Scanner (`src/converge/scanner`)
The scanner extracts real relationships by reading files:
- `project.py`: Naively parses `requirements.txt` and `pyproject.toml` into `Package` nodes and `REQUIRES` edges.
- `ast_parser.py`: Uses `ast.parse` to find `import X` and maps them to `IMPORTS` edges.
- `service_detector.py`: Scans AST for routes (e.g. `@app.get`).

## 3. Solver (`src/converge/solver`)
The determinisic resolution engine:
- `ConflictDetector`: Finds unresolved imports or misaligned version constraints.
- `RepairPlanner`: Emits `RepairPlan`s composed of `RepairAction`s (`ADD_DEPENDENCY`, `PIN_VERSION`).

## 4. Validation (`src/converge/validation`)
Converge uses `uv` securely isolated.
- `UVSandbox`: Wraps `uv venv` and `uv pip install` to safely test a plan.
- `ValidationRunner`: Tries a plan in the sandbox and verifies via smoke imports (checking `import target` via subprocess).

## Modifying Converge
- When adding entities, update `src/converge/models.py`.
- ALWAYS test via the CLI (`converge scan .`, `converge fix .`).
