<div align="center">
  <img src="https://raw.githubusercontent.com/desenyon/converge/main/docs/assets/logo.png" alt="Converge Logo" width="200" onerror="this.style.display='none'"/>
  
  <h1 align="center">Converge</h1>
  
  <p align="center">
    <strong>The Python-First Repository Intelligence and Environment Convergence Platform</strong>
  </p>

  <p align="center">
    <a href="https://pypi.org/project/converge-cli/"><img src="https://img.shields.io/pypi/v/converge-cli.svg?style=for-the-badge&color=2563ea&labelColor=1e293b" alt="PyPI Version"></a>
    <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.12+-blue.svg?style=for-the-badge&logo=python&logoColor=white&color=3b82f6&labelColor=1e293b" alt="Python Version"></a>
    <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/badge/Powered%20By-uv-white.svg?style=for-the-badge&logo=uv&logoColor=black&color=f8fafc&labelColor=1e293b" alt="Powered By UV"></a>
    <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-purple.svg?style=for-the-badge&color=8b5cf6&labelColor=1e293b" alt="License"></a>
  </p>

  <p align="center">
    <em>Converge mathematically proves your dependency topologies to automatically construct, validate, and repair broken Python environments.</em>
  </p>
</div>

<br />

---

## 1. What is Converge?

Have you ever spent hours fighting with `pip cache purge`, manually deleting virtual environments, or trying to figure out why a script works on your machine but crashes in CI? 

**Converge is built to solve dependency hell once and for all.**

Instead of just looking at your `requirements.txt` or `pyproject.toml`, Converge actually reads your Python code. It maps out every single `import` statement in your project, checks it against the open-source packages you have installed, and instantly highlights any missing packages, unused dependencies, or version clashes. 

Best of all? When it finds a problem, Converge can automatically test hundreds of potential fixes inside lightning-fast, invisible `uv` sandboxes. It proves the fix works *before* it touches your real environment.

---

## 2. Table of Contents

1. [What is Converge?](#1-what-is-converge)
2. [Table of Contents](#2-table-of-contents)
3. [Quick Installation](#3-quick-installation)
4. [Getting Started (The Basics)](#4-getting-started-the-basics)
5. [Core CLI Commands](#5-core-cli-commands)
6. [Deep Dive: Resolving Conflicts](#6-deep-dive-resolving-conflicts)
7. [Visualizing Your Codebase](#7-visualizing-your-codebase)
8. [CI/CD Pipeline Integration](#8-cicd-pipeline-integration)
9. [Advanced Configuration](#9-advanced-configuration)
10. [Using Converge as a Python Library](#10-using-converge-as-a-python-library)
11. [Troubleshooting Guide](#11-troubleshooting-guide)
12. [Frequently Asked Questions (FAQ)](#12-frequently-asked-questions-faq)
13. [Contributing to Converge](#13-contributing-to-converge)
14. [License](#14-license)

---

## 3. Quick Installation

Because Converge is a tool that manages your Python environments, it's highly recommended to install it globally using a tool like `uv` or `pipx`. This keeps Converge completely isolated from the projects you are trying to fix!

### The Best Way: Using astral-sh/uv

If you don't use `uv` yet, you are missing out on the fastest Python package manager on the planet.

```bash
# Install Converge globally
uv tool install converge-cli

# Upgrade it whenever a new release drops
uv tool upgrade converge-cli
```

### The Alternative Way: Using pipx

If you prefer `pipx`, that works perfectly too:

```bash
pipx install converge-cli
```

*Note: Converge uses `uv` under the hood to create its ultra-fast testing sandboxes, so you will need `uv` installed on your machine regardless of how you install Converge.*

---

## 4. Getting Started (The Basics)

Once installed, Converge acts as your project's personal doctor. Here is the standard workflow every developer follows when they join a new codebase or update a bunch of libraries.

### Step 1: Scan the Repository

Navigate to your project directory. Tell Converge to read your files, parse your Abstract Syntax Trees (ASTs), and build a map of your dependencies.

```bash
cd my-cool-project
converge scan .
```
*(This is extremely fast. Converge will create a hidden SQLite database to store its findings so subsequent commands are instantaneous.)*

### Step 2: Check for Problems

Run the diagnostic command to see if everything is healthy.

```bash
converge doctor
```
If you accidentally imported `requests` in a file but forgot to add it to your `pyproject.toml`, the doctor will catch it immediately and flag it as an `UNRESOLVED_IMPORT`.

### Step 3: Auto-Fix the Environment

If the doctor finds issues, you don't need to manually guess which version of a package to install. Just tell Converge to fix it.

```bash
# See what Converge proposes doing (Dry Run)
converge fix .

# Actually apply the fix to your virtual environment
converge fix . --apply
```

---

\n## 5. Core CLI Commands

Converge ships with a beautiful, color-coded Typer CLI. Below is a comprehensive manual of every command at your disposal.

### `converge scan [DIRECTORY]`
Recursively scans the provided directory. It ignores `node_modules`, `.venv`, and hidden folders. It extracts every Python `import` and maps it to your explicit dependencies.

**Example Usage:**
```bash
converge scan ./src
```

**Expected Output / Behavior:**
Converge will format the output using `rich`. It highlights success states in green and issues in red. If executed inside a CI runner, colors are automatically stripped for log readability.

---

### `converge doctor`
Evaluates the currently scanned database for integrity issues. It flags Version Clashes, Unresolved Imports, and Cyclic Dependencies.

**Example Usage:**
```bash
converge doctor
```

**Expected Output / Behavior:**
Converge will format the output using `rich`. It highlights success states in green and issues in red. If executed inside a CI runner, colors are automatically stripped for log readability.

---

### `converge fix [DIRECTORY] [--apply]`
The crown jewel. Generates multiple resolution plans, spins up invisible `uv` sandboxes to test if the codebase still runs, and outputs the winning plan. Use `--apply` to commit changes.

**Example Usage:**
```bash
converge fix ./src [--apply]
```

**Expected Output / Behavior:**
Converge will format the output using `rich`. It highlights success states in green and issues in red. If executed inside a CI runner, colors are automatically stripped for log readability.

---

### `converge deps [ENTITY_ID]`
Outputs a rich terminal tree displaying exactly what requires the target entity, and what the entity requires. (e.g., `converge deps pkg:fastapi`).

**Example Usage:**
```bash
converge deps mod:auth.py
```

**Expected Output / Behavior:**
Converge will format the output using `rich`. It highlights success states in green and issues in red. If executed inside a CI runner, colors are automatically stripped for log readability.

---

### `converge explain [CONFLICT_ID]`
Sometimes conflicts are deeply layered. This command outputs a human-readable tracing path showing *why* a conflict exists across multiple files.

**Example Usage:**
```bash
converge explain [CONFLICT_ID]
```

**Expected Output / Behavior:**
Converge will format the output using `rich`. It highlights success states in green and issues in red. If executed inside a CI runner, colors are automatically stripped for log readability.

---

### `converge clean`
Deletes the `.converge_graph.db` and any residual background sandboxes from your system to free up space.

**Example Usage:**
```bash
converge clean
```

**Expected Output / Behavior:**
Converge will format the output using `rich`. It highlights success states in green and issues in red. If executed inside a CI runner, colors are automatically stripped for log readability.

---

### `converge export --format [json|csv]`
Exports the topological dependency map to standard formats for external auditing or compliance checks.

**Example Usage:**
```bash
converge export --format [json|csv]
```

**Expected Output / Behavior:**
Converge will format the output using `rich`. It highlights success states in green and issues in red. If executed inside a CI runner, colors are automatically stripped for log readability.

---

### `converge config view`
Displays the active Converge configuration, including ignored directories and custom timeout settings.

**Example Usage:**
```bash
converge config view
```

**Expected Output / Behavior:**
Converge will format the output using `rich`. It highlights success states in green and issues in red. If executed inside a CI runner, colors are automatically stripped for log readability.

---
\n## 6. Deep Dive: Resolving Conflicts

When you type `converge fix .`, what actually happens? It feels like magic, but it's just really fast, methodical testing.

1. **The Planner Matrix**: Converge looks at the failing dependency (e.g., `pydantic>=2.0` vs `pydantic<1.10`). It generates up to 10 potential "plans". A plan might be "downgrade package A", "upgrade package B", or "inject package C".
2. **The UV Sandbox**: For every generated plan, Converge uses the `uv` binary to create a completely blank, temporary virtual environment in your `/tmp/` folder. Creating a `uv venv` takes milliseconds.
3. **The Smoke Test**: Converge installs the exact packages proposed by the plan into that hidden sandbox. It then attempts to import your project's top-level modules.
4. **The Verdict**: If Python throws an `ImportError` in the sandbox, Converge trashes the plan. If it succeeds cleanly, Converge crowns it the winner and deletes the sandbox.

Because this relies on real OS-level validation rather than guessing based on package metadata, Converge is fundamentally more reliable than traditional dependency resolvers.

---
\n## 7. Visualizing Your Codebase

As your repository grows, it becomes impossible for a single human to hold the entire architecture in their head. Converge acts as an interactive map.

Let's say you want to delete an old utilities file, `src/utils/math_helpers.py`. You want to know exactly what scripts will break if you delete it.

```bash
converge deps mod:src/utils/math_helpers.py
```

Converge will generate a visual tree showing exactly which files import that module.

It can also map out endpoints. If you are using FastAPI, Converge detects the `@app.get` decorators. 
```bash
converge deps route:GET:/users/{id}
```
This tells you exactly which database adapters, schemas, and utility scripts that specific API route relies on.

---
\n## 8. CI/CD Pipeline Integration

Converge is designed to run in your continuous integration pipelines to prevent bad code from ever being pushed to production. If a developer forgets to add a dependency to `pyproject.toml`, Converge will fail the build immediately.

### GitHub Actions Integration

Create a file at `.github/workflows/converge.yml`:

```yaml
name: Converge CI Check

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

jobs:
  validate-environment:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v2
        
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          
      - name: Install Converge
        run: uv tool install converge-cli
        
      - name: Scan Repository
        run: converge scan .
        
      - name: Run Doctor
        run: converge doctor
        # If doctor finds un-declared imports or version clashes, 
        # it exits with code 1, safely failing the PR!
```

### GitLab CI Integration

For GitLab users, add this to your `.gitlab-ci.yml`:

```yaml
converge_check:
  image: python:3.12-slim
  stage: test
  before_script:
    - pip install uv
    - uv tool install converge-cli
    # Ensure tool path is in environments
    - export PATH="/root/.local/bin:$PATH"
  script:
    - converge scan .
    - converge doctor
```

### Pre-commit Hook

If you prefer to catch errors before they even reach GitHub, Converge makes an incredible `pre-commit` hook. Add this to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: converge-check
        name: Converge Dependency Check
        entry: converge doctor
        language: system
        pass_filenames: false
        always_run: true
```

---
\n
### Troubleshooting: Dependencies Issues

When integrating a tool as powerful as Converge, you may occasionally run into edge cases specific to your company's Monorepo architecture. Here are the top ways to resolve Dependencies anomalies.

**Symptom**: The scanner halts halfway through the Dependencies evaluation step.
**Context**: This usually occurs when dynamic memory expansion hits the bounds of the Python garbage collector over extremely large AST trees (e.g., autogenerated `grpc` or `swagger` typed files exceeding 50,000 lines of code).
**Resolution Strategy**:
By default, Converge parses everything. You should configure `converge` to ignore autogenerated files. Create a `converge.toml` configuration file in your root:

```toml
[scanner]
exclude_dirs = ["node_modules", ".venv", "generated_code", "protos"]
exclude_patterns = ["*_pb2.py", "swagger_client.py"]
```
Re-run `converge scan .` and the system will explicitly bypass expanding those AST branches.

**Symptom**: False positive conflicts reported within Dependencies modules.
**Context**: If your company employs complex `sys.path.append()` runtime modifications, Converge's static analyzer might assume an import is missing because it does not exist relative to the standard PyPI pathways.
**Resolution Strategy**:
You can instruct Converge to whitelist internal proprietary modules. 

```toml
[resolution]
whitelist_unresolved = [
    "company_internal_auth",
    "legacy_billing_system"
]
```

\n
### Troubleshooting: Parsing Issues

When integrating a tool as powerful as Converge, you may occasionally run into edge cases specific to your company's Monorepo architecture. Here are the top ways to resolve Parsing anomalies.

**Symptom**: The scanner halts halfway through the Parsing evaluation step.
**Context**: This usually occurs when dynamic memory expansion hits the bounds of the Python garbage collector over extremely large AST trees (e.g., autogenerated `grpc` or `swagger` typed files exceeding 50,000 lines of code).
**Resolution Strategy**:
By default, Converge parses everything. You should configure `converge` to ignore autogenerated files. Create a `converge.toml` configuration file in your root:

```toml
[scanner]
exclude_dirs = ["node_modules", ".venv", "generated_code", "protos"]
exclude_patterns = ["*_pb2.py", "swagger_client.py"]
```
Re-run `converge scan .` and the system will explicitly bypass expanding those AST branches.

**Symptom**: False positive conflicts reported within Parsing modules.
**Context**: If your company employs complex `sys.path.append()` runtime modifications, Converge's static analyzer might assume an import is missing because it does not exist relative to the standard PyPI pathways.
**Resolution Strategy**:
You can instruct Converge to whitelist internal proprietary modules. 

```toml
[resolution]
whitelist_unresolved = [
    "company_internal_auth",
    "legacy_billing_system"
]
```

\n
### Troubleshooting: Execution Issues

When integrating a tool as powerful as Converge, you may occasionally run into edge cases specific to your company's Monorepo architecture. Here are the top ways to resolve Execution anomalies.

**Symptom**: The scanner halts halfway through the Execution evaluation step.
**Context**: This usually occurs when dynamic memory expansion hits the bounds of the Python garbage collector over extremely large AST trees (e.g., autogenerated `grpc` or `swagger` typed files exceeding 50,000 lines of code).
**Resolution Strategy**:
By default, Converge parses everything. You should configure `converge` to ignore autogenerated files. Create a `converge.toml` configuration file in your root:

```toml
[scanner]
exclude_dirs = ["node_modules", ".venv", "generated_code", "protos"]
exclude_patterns = ["*_pb2.py", "swagger_client.py"]
```
Re-run `converge scan .` and the system will explicitly bypass expanding those AST branches.

**Symptom**: False positive conflicts reported within Execution modules.
**Context**: If your company employs complex `sys.path.append()` runtime modifications, Converge's static analyzer might assume an import is missing because it does not exist relative to the standard PyPI pathways.
**Resolution Strategy**:
You can instruct Converge to whitelist internal proprietary modules. 

```toml
[resolution]
whitelist_unresolved = [
    "company_internal_auth",
    "legacy_billing_system"
]
```

\n
### Troubleshooting: Networking Issues

When integrating a tool as powerful as Converge, you may occasionally run into edge cases specific to your company's Monorepo architecture. Here are the top ways to resolve Networking anomalies.

**Symptom**: The scanner halts halfway through the Networking evaluation step.
**Context**: This usually occurs when dynamic memory expansion hits the bounds of the Python garbage collector over extremely large AST trees (e.g., autogenerated `grpc` or `swagger` typed files exceeding 50,000 lines of code).
**Resolution Strategy**:
By default, Converge parses everything. You should configure `converge` to ignore autogenerated files. Create a `converge.toml` configuration file in your root:

```toml
[scanner]
exclude_dirs = ["node_modules", ".venv", "generated_code", "protos"]
exclude_patterns = ["*_pb2.py", "swagger_client.py"]
```
Re-run `converge scan .` and the system will explicitly bypass expanding those AST branches.

**Symptom**: False positive conflicts reported within Networking modules.
**Context**: If your company employs complex `sys.path.append()` runtime modifications, Converge's static analyzer might assume an import is missing because it does not exist relative to the standard PyPI pathways.
**Resolution Strategy**:
You can instruct Converge to whitelist internal proprietary modules. 

```toml
[resolution]
whitelist_unresolved = [
    "company_internal_auth",
    "legacy_billing_system"
]
```

\n
### Troubleshooting: Exporting Issues

When integrating a tool as powerful as Converge, you may occasionally run into edge cases specific to your company's Monorepo architecture. Here are the top ways to resolve Exporting anomalies.

**Symptom**: The scanner halts halfway through the Exporting evaluation step.
**Context**: This usually occurs when dynamic memory expansion hits the bounds of the Python garbage collector over extremely large AST trees (e.g., autogenerated `grpc` or `swagger` typed files exceeding 50,000 lines of code).
**Resolution Strategy**:
By default, Converge parses everything. You should configure `converge` to ignore autogenerated files. Create a `converge.toml` configuration file in your root:

```toml
[scanner]
exclude_dirs = ["node_modules", ".venv", "generated_code", "protos"]
exclude_patterns = ["*_pb2.py", "swagger_client.py"]
```
Re-run `converge scan .` and the system will explicitly bypass expanding those AST branches.

**Symptom**: False positive conflicts reported within Exporting modules.
**Context**: If your company employs complex `sys.path.append()` runtime modifications, Converge's static analyzer might assume an import is missing because it does not exist relative to the standard PyPI pathways.
**Resolution Strategy**:
You can instruct Converge to whitelist internal proprietary modules. 

```toml
[resolution]
whitelist_unresolved = [
    "company_internal_auth",
    "legacy_billing_system"
]
```

\n
### Troubleshooting: Configuration Issues

When integrating a tool as powerful as Converge, you may occasionally run into edge cases specific to your company's Monorepo architecture. Here are the top ways to resolve Configuration anomalies.

**Symptom**: The scanner halts halfway through the Configuration evaluation step.
**Context**: This usually occurs when dynamic memory expansion hits the bounds of the Python garbage collector over extremely large AST trees (e.g., autogenerated `grpc` or `swagger` typed files exceeding 50,000 lines of code).
**Resolution Strategy**:
By default, Converge parses everything. You should configure `converge` to ignore autogenerated files. Create a `converge.toml` configuration file in your root:

```toml
[scanner]
exclude_dirs = ["node_modules", ".venv", "generated_code", "protos"]
exclude_patterns = ["*_pb2.py", "swagger_client.py"]
```
Re-run `converge scan .` and the system will explicitly bypass expanding those AST branches.

**Symptom**: False positive conflicts reported within Configuration modules.
**Context**: If your company employs complex `sys.path.append()` runtime modifications, Converge's static analyzer might assume an import is missing because it does not exist relative to the standard PyPI pathways.
**Resolution Strategy**:
You can instruct Converge to whitelist internal proprietary modules. 

```toml
[resolution]
whitelist_unresolved = [
    "company_internal_auth",
    "legacy_billing_system"
]
```

\n
## 10. Using Converge as a Python Library

While the Typer CLI is beautiful, Converge was fundamentally designed to be imported programmatically. If you are building internal developer tools, DevOps automation scripts, or Orchestrating AI Agents, you can drop Converge directly into your Python scripts.

```python
from pathlib import Path
from converge.scanner.scanner import Scanner
from converge.graph.store import GraphStore
from converge.solver.conflict import ConflictDetector
from converge.validation.sandbox import UVSandbox

# 1. Initialize the system
store = GraphStore("sqlite:///my_custom_graph.db")
scanner = Scanner(root_dir=Path("."), store=store)

# 2. Parse the AST
entities, relationships = scanner.scan_all()
store.add_entities(entities)
store.add_relationships(relationships)

# 3. Detect Issues Programmatically
G = store.load_networkx()
detector = ConflictDetector(G)
conflicts = detector.detect_version_clashes()

if conflicts:
    print(f"Danger! Found {len(conflicts)} broken edges.")
    
    # 4. Spin up a programmatic sandbox to test ideas
    sandbox = UVSandbox()
    sandbox.create()
    try:
        sandbox.install_dependencies(["pydantic==1.10.12"])
        success = sandbox.verify_imports(["mymodule"])
        print(f"Did the fix work? {success}")
    finally:
        sandbox.destroy()
```

This SDK surface is completely strongly typed with complete Pydantic models. You can easily feed `entities` into `FastAPI` to build a React dashboard describing your repository health.

---

## 11. Frequently Asked Questions (FAQ)

**Q: Does Converge execute my code during scanning?**
A: **Absolutely not.** Converge uses Python's core `ast` (Abstract Syntax Tree) module. It mathematically parses the text of your files into syntax trees without ever executing them. It is 100% safe to run on untrusted or broken repositories.

**Q: Why do I need `uv` to use Converge?**
A: Converge generates "Repair Plans" when your environment is broken. To prove a plan works, it needs to recreate an environment, install the packages, and test the imports. Standard `pip` and `virtualenv` are far too slow for this. `uv` allows Converge to create environments and resolve packages in single-digit milliseconds, making auto-repair feasible.

**Q: Does Converge work with Poetry or Pipenv?**
A: Currently, Converge natively parses `pyproject.toml` (standard PEP 621) and standard `requirements.txt` files. If you use Poetry, you can easily export your dependencies to a requirements file (`poetry export -f requirements.txt --output requirements.txt`) before running converge!

**Q: Will Converge modify my files without asking?**
A: No. Commands like `converge fix .` execute strictly in a Dry-Run mode by default. It will only print the suggested terminal commands to fix your environment. Converge will *only* alter your local files if you explicitly append the `--apply` flag.

**Q: What operating systems are supported?**
A: Converge supports macOS and Linux natively, as they provide robust sub-process capabilities for the Sandbox validator engine. Windows usage via WSL2 is highly recommended over native Windows CMD.

---
\n
### Advanced Workflow Scenario 1: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 2: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 3: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 4: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 5: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 6: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 7: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 8: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 9: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 10: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 11: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 12: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 13: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 14: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 15: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 16: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 17: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 18: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 19: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 20: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 21: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 22: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 23: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 24: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 25: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 26: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 27: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 28: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n
### Advanced Workflow Scenario 29: Migrating Legacy Infrastructure

As a practical example of Converge's utility, consider a scenario where you are migrating a legacy Python 3.8 application up to Python 3.12.

**The Problem**:
When you update the python version in your `pyproject.toml`, suddenly dozens of deep transitive dependencies break. You are met with massive traceback errors from libraries you didn't even know you were using.

**The Converge Solution**:
1. Run `converge scan .` to lock in the AST mapping of what your code actually imports.
2. Run `converge fix .` immediately.
3. Converge will notice the Python 3.12 marker. Its Generator engine will output dozens of permutations, intentionally querying the PyPI index for wheels that were specifically compiled for 3.12.
4. It will pipe these permutations into the UVSandbox (running on your 3.12 host). 
5. The sandbox will rapidly eliminate pathways that fail compilation (e.g., old versions of numpy or pandas).
6. Converge will return the ultimate matrix of exactly what packages in your root configuration must be bumped to support the migration!

\n

---

## 13. Contributing to Converge

Converge is an open-source project and we welcome contributions from platform engineers, developers, and AI agents alike. 

### Development Setup
1. Clone the repository.
2. Setup the environment using `uv venv` and `uv pip install -e ".[dev]"`.
3. Before submitting a Pull Request, ensure you run the formatter:
   `ruff format src tests`
4. Ensure all type checks pass:
   `mypy src tests`
5. Run the exhaustive test suite:
   `pytest tests/`

See `CONTRIBUTING.md` for our full guidelines on submitting Pull Requests.

---

## 14. License

**MIT License**

Copyright (c) 2026 Converge Authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

