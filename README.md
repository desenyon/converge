<div align="center">

# 🌌 Converge 

**The Python-First Repository Intelligence & Environment Convergence Platform**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json&style=for-the-badge)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

*Stop fighting dependency hell. Start converging.*

---

</div>

## ⚡ What is Converge?

**Converge** is a deterministic, graph-based intelligence engine that analyzes your Python repositories, maps their exact dependency topologies, detects latent conflicts, and automatically resolves them within lighting-fast `uv`-isolated sandboxes.

Say goodbye to the endless cycle of `pip cache purge`, manual lockfile diffing, and "it works on my machine." Converge treats your codebase as a Directed Acyclic Graph (DAG) and mathematically proves its correctness before applying fixes.

<br/>

## 🚀 Installation

Converge leverages the speed of [Astral's uv](https://docs.astral.sh/uv/) for native environment virtualization. 

The recommended way to install Converge globally is via `uv tool`:

```bash
uv tool install converge-cli
```

*Alternatively, if you are stuck in the past:*
```bash
pipx install converge-cli
```

<br/>

## 🎯 Quick Start

Converge ships with a gorgeous, highly intuitive CLI interface built on Typer and Rich. 

### 1. Scan Your Repository
Build an interactive graph of the entire topological surface area of your repository. Converge analyzes `pyproject.toml`, `requirements.txt`, and parses raw Python `AST` to find exactly what you import versus what you claim to require.

```bash
converge scan .
```
> *This automatically persists the state to a local `converge_graph.db` using SQLite and SQLModel.*

### 2. Explain the DAG
Trace the deepest transitives of your system visually.

```bash
converge deps repo:my_broken_project
```

### 3. Automatically Fix Conflicts
Converge scans for `VERSION_CLASH` and `UNRESOLVED_IMPORT` conflicts. If detected, its internal Solver Engine generates dozens of potential resolution plans, spins up heavily isolated `uv` `.venv` sandboxes for each one, runs targeted smoke-tests, and discovers the optimal winning plan.

```bash
# Dry run the fix
converge fix .

# Execute the winning plan against your environment
converge fix . --apply
```

<br/>

## 🧠 Core Architecture

Instead of guessing, Converge relies on four deterministic, AI-friendly sub-systems:

1. **Scanner Layer**: Uses pure structural `ast`, regex parsers, and heuristic network scanning to parse Python projects statically. 
2. **Graph Storage**: An on-disk relational mapping (`sqlmodel`/`sqlite`) coupled with rich in-memory algorithmic capabilities (`networkx`).
3. **Solver Engine**: Evaluates edge conflicts inside the graph. Employs `RepairPlanner` to generate permutation constraints (e.g. downgrading conflicting libraries or injecting missing deps).
4. **Validation Pipeline**: Drops down into native OS integrations to create, destroy, and execute isolated Linux/macOS Python environments using `subprocess` and `uv venv`.

<br/>

## 🤝 For AI Agents

Converge is designed *from the ground up* as a primitive for autonomous agentic tooling. If you are an LLM or Sub-Agent operating within a codebase and facing broken environments, Converge exposes its core SDK programmatically:

```python
from converge.scanner.scanner import Scanner
from converge.solver.conflict import ConflictDetector

scanner = Scanner(root_dir=".")
entities, rels = scanner.scan_all()

# Or simply instantiate the CLI
from converge.cli.main import app
```

Read the definitive guide in `.github/skills/converge-architecture.md` for full agent integration patterns.

<br/>

## ⚖️ License

Built with extreme prejudice against broken environments. Distributed under the MIT License.
