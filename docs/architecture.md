# Converge Architecture

Converge is broken down into a pipeline of discrete engines.

## 1. Scanner Layer
Reads the environment, extracting data without modifying it.
- **ProjectScanner**: Parses `pyproject.toml` and `requirements.txt`.
- **ASTParser**: Parses `*.py` files looking for `ast.Import` nodes.
- **ServiceDetector**: Parses `ast.FunctionDef` looking for HTTP route decorators.

## 2. Graph Layer
- Backed by SQLite via `SQLModel` for durability between runs.
- Loaded into memory via `networkx` for fast algorithmic traversal.

## 3. Solver Layer
- **ConflictDetector**: Runs queries (like missing relationships or version mismatches).
- **RepairPlanner**: Translates conflicts into actionable `RepairPlan`s.

## 4. Validation Engine
- Leverages `uv` to instantiate dynamic `venv` sandboxes.
- Modifies the isolated environment to reflect the `RepairPlan`.
- Validates the fix using sub-process Python smoke imports.
