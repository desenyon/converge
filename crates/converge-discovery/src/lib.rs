//! Read-only repository and host discovery.

use std::collections::BTreeSet;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::str::FromStr;
use std::time::{Duration, Instant};

use converge_core::ConvergeError;
use converge_model::{
    Confidence, DependencyFile, DiscoverySnapshot, Evidence, ImportEvidence, LockedPackage,
    PythonProject, PythonRequirement, ToolEvidence, WorkspaceEvidence,
};
use pep508_rs::Requirement;
use time::OffsetDateTime;
use tree_sitter::{Node, Parser};
use uuid::Uuid;
use walkdir::WalkDir;
use yaml_rust2::{Yaml, YamlLoader};

/// Resolve and validate the explicit repository target.
///
/// # Errors
///
/// Returns a discovery error when the target is absent, inaccessible, or not a directory.
pub fn resolve_target(path: impl AsRef<Path>) -> Result<PathBuf, ConvergeError> {
    let path = path.as_ref();
    let metadata = std::fs::metadata(path)
        .map_err(|error| ConvergeError::Discovery(format!("{}: {error}", path.display())))?;
    if !metadata.is_dir() {
        return Err(ConvergeError::Discovery(format!(
            "target is not a directory: {}",
            path.display()
        )));
    }
    path.canonicalize()
        .map_err(|error| ConvergeError::Discovery(error.to_string()))
}

/// Produce a deterministic, read-only discovery snapshot.
///
/// # Errors
///
/// Returns a discovery error when the explicit target cannot be resolved or evidence cannot be read.
pub fn discover(path: impl AsRef<Path>) -> Result<DiscoverySnapshot, ConvergeError> {
    let target = resolve_target(path)?;
    let files = relevant_files(&target)?;
    let mut snapshot = DiscoverySnapshot::empty(target.to_string_lossy());
    snapshot.run_id = Uuid::new_v4();
    snapshot.observed_at = OffsetDateTime::now_utc();
    snapshot.repository.source_fingerprint = fingerprint_files(&target, &files)?;

    snapshot.evidence.push(Evidence {
        id: "repository-target".to_owned(),
        kind: "repositoryBoundary".to_owned(),
        source: target.to_string_lossy().into_owned(),
        observation: "explicit target resolved to an existing directory".to_owned(),
        confidence: Confidence::Certain,
    });

    for path in &files {
        ingest_file(&target, path, &mut snapshot)?;
    }

    record_multi_project_workspace(&mut snapshot);
    sort_and_deduplicate(&mut snapshot);
    detect_python_tools(&mut snapshot);
    Ok(snapshot)
}

fn ingest_file(
    target: &Path,
    path: &Path,
    snapshot: &mut DiscoverySnapshot,
) -> Result<(), ConvergeError> {
    let relative = relative_path(target, path);
    let content = std::fs::read_to_string(path).map_err(|error| {
        ConvergeError::Discovery(format!("cannot read {}: {error}", path.display()))
    })?;
    let content_fingerprint = blake3::hash(content.as_bytes()).to_hex().to_string();

    match path.file_name().and_then(|name| name.to_str()) {
        Some("pyproject.toml") => {
            snapshot.manifests.push(DependencyFile {
                path: relative.clone(),
                format: "pyproject.toml".to_owned(),
                fingerprint: content_fingerprint,
            });
            match parse_pyproject(target, &relative, &content) {
                Ok((project, workspace)) => {
                    snapshot.projects.push(project);
                    if let Some(workspace) = workspace {
                        snapshot.workspaces.push(workspace);
                    }
                }
                Err(error) => snapshot.warnings.push(format!("{relative}: {error}")),
            }
        }
        Some("uv.lock") => {
            ingest_toml_lock(
                snapshot,
                &relative,
                "uv.lock",
                content_fingerprint,
                &content,
            );
        }
        Some("poetry.lock") => {
            ingest_toml_lock(
                snapshot,
                &relative,
                "poetry.lock",
                content_fingerprint,
                &content,
            );
        }
        Some(name) if is_conda_environment_file(name) => {
            snapshot.manifests.push(DependencyFile {
                path: relative.clone(),
                format: "conda.environment".to_owned(),
                fingerprint: content_fingerprint,
            });
            match parse_conda_environment(&relative, &content) {
                Ok(project) => snapshot.projects.push(project),
                Err(error) => snapshot.warnings.push(format!("{relative}: {error}")),
            }
        }
        Some(name) if is_requirements_file(name) => {
            snapshot.manifests.push(DependencyFile {
                path: relative.clone(),
                format: "requirements".to_owned(),
                fingerprint: content_fingerprint,
            });
            let requirements = parse_requirements(&relative, &content, &mut snapshot.warnings);
            snapshot.projects.push(PythonProject {
                manifest_path: relative,
                name: None,
                requires_python: None,
                backend: "requirements".to_owned(),
                dependencies: requirements,
            });
        }
        Some(_) if has_extension(path, "py") => match parse_python_imports(&relative, &content) {
            Ok(imports) => snapshot.imports.extend(imports),
            Err(error) => snapshot.warnings.push(format!("{relative}: {error}")),
        },
        _ => {}
    }
    Ok(())
}

fn ingest_toml_lock(
    snapshot: &mut DiscoverySnapshot,
    relative: &str,
    format: &str,
    fingerprint: String,
    content: &str,
) {
    snapshot.lockfiles.push(DependencyFile {
        path: relative.to_owned(),
        format: format.to_owned(),
        fingerprint,
    });
    match parse_toml_package_lock(relative, content) {
        Ok(packages) => snapshot.locked_packages.extend(packages),
        Err(error) => snapshot.warnings.push(format!("{relative}: {error}")),
    }
}

fn relevant_files(target: &Path) -> Result<Vec<PathBuf>, ConvergeError> {
    let mut files = Vec::new();
    for entry in WalkDir::new(target)
        .follow_links(false)
        .into_iter()
        .filter_entry(|entry| {
            entry.depth() == 0
                || !entry.file_type().is_dir()
                || !ignored_directory(entry.file_name().to_str())
        })
    {
        let entry = entry.map_err(|error| ConvergeError::Discovery(error.to_string()))?;
        if entry.file_type().is_file() && is_relevant_file(entry.path()) {
            files.push(entry.into_path());
        }
    }
    files.sort_by_key(|path| relative_path(target, path));
    Ok(files)
}

fn ignored_directory(name: Option<&str>) -> bool {
    matches!(
        name,
        Some(".git" | ".converge" | ".venv" | "node_modules" | "target" | "__pycache__")
    )
}

fn is_relevant_file(path: &Path) -> bool {
    let Some(name) = path.file_name().and_then(|name| name.to_str()) else {
        return false;
    };
    name == ".converge.toml"
        || name == "uv.toml"
        || name == ".python-version"
        || name == "pyproject.toml"
        || name == "uv.lock"
        || name == "poetry.lock"
        || has_extension(path, "py")
        || is_requirements_file(name)
        || is_conda_environment_file(name)
}

fn is_requirements_file(name: &str) -> bool {
    let extension = Path::new(name).extension().and_then(|value| value.to_str());
    (name.starts_with("requirements")
        && extension.is_some_and(|value| {
            value.eq_ignore_ascii_case("txt") || value.eq_ignore_ascii_case("in")
        }))
        || name == "constraints.txt"
}

fn is_conda_environment_file(name: &str) -> bool {
    name.eq_ignore_ascii_case("environment.yml") || name.eq_ignore_ascii_case("environment.yaml")
}

fn has_extension(path: &Path, expected: &str) -> bool {
    path.extension()
        .and_then(|value| value.to_str())
        .is_some_and(|value| value.eq_ignore_ascii_case(expected))
}

fn fingerprint_files(target: &Path, files: &[PathBuf]) -> Result<String, ConvergeError> {
    let mut hasher = blake3::Hasher::new();
    for path in files {
        hasher.update(relative_path(target, path).as_bytes());
        hasher.update(&[0]);
        let bytes = std::fs::read(path)
            .map_err(|error| ConvergeError::Discovery(format!("{}: {error}", path.display())))?;
        hasher.update(&bytes);
        hasher.update(&[0]);
    }
    Ok(hasher.finalize().to_hex().to_string())
}

fn relative_path(target: &Path, path: &Path) -> String {
    path.strip_prefix(target)
        .unwrap_or(path)
        .to_string_lossy()
        .replace('\\', "/")
}

fn parse_pyproject(
    target: &Path,
    path: &str,
    content: &str,
) -> Result<(PythonProject, Option<WorkspaceEvidence>), String> {
    let value: toml::Value = toml::from_str(content).map_err(|error| error.to_string())?;
    let project_table = value.get("project").and_then(toml::Value::as_table);
    let poetry = value
        .get("tool")
        .and_then(toml::Value::as_table)
        .and_then(|tool| tool.get("poetry"))
        .and_then(toml::Value::as_table);

    let mut name = project_table
        .and_then(|table| table.get("name"))
        .and_then(toml::Value::as_str)
        .map(ToOwned::to_owned);
    let mut requires_python = project_table
        .and_then(|table| table.get("requires-python"))
        .and_then(toml::Value::as_str)
        .map(ToOwned::to_owned);

    let mut dependencies = Vec::new();
    let mut backend = "pep621".to_owned();

    if let Some(items) = project_table
        .and_then(|table| table.get("dependencies"))
        .and_then(toml::Value::as_array)
    {
        dependencies.extend(parse_requirement_array(path, "default", items)?);
    }
    if let Some(groups) = value
        .get("dependency-groups")
        .and_then(toml::Value::as_table)
    {
        for (group, items) in groups {
            if let Some(items) = items.as_array() {
                dependencies.extend(parse_requirement_array(path, group, items)?);
            }
        }
    }

    if let Some(poetry) = poetry {
        backend = if project_table.is_some() {
            "pep621+poetry".to_owned()
        } else {
            "poetry".to_owned()
        };
        if name.is_none() {
            name = poetry
                .get("name")
                .and_then(toml::Value::as_str)
                .map(ToOwned::to_owned);
        }
        if requires_python.is_none() {
            requires_python = poetry
                .get("dependencies")
                .and_then(toml::Value::as_table)
                .and_then(|deps| deps.get("python"))
                .and_then(poetry_python_constraint);
        }
        if let Some(deps) = poetry.get("dependencies").and_then(toml::Value::as_table) {
            dependencies.extend(parse_poetry_dependency_table(path, "default", deps)?);
        }
        if let Some(groups) = poetry.get("group").and_then(toml::Value::as_table) {
            for (group, body) in groups {
                if let Some(deps) = body
                    .as_table()
                    .and_then(|table| table.get("dependencies"))
                    .and_then(toml::Value::as_table)
                {
                    dependencies.extend(parse_poetry_dependency_table(path, group, deps)?);
                }
            }
        }
        if let Some(dev) = poetry
            .get("dev-dependencies")
            .and_then(toml::Value::as_table)
        {
            dependencies.extend(parse_poetry_dependency_table(path, "dev", dev)?);
        }
    }

    if project_table.is_none() && poetry.is_none() {
        "pyproject".clone_into(&mut backend);
    }

    dedupe_requirements(&mut dependencies);
    dependencies.sort_by(|left, right| {
        (&left.group, &left.normalized_name, &left.raw).cmp(&(
            &right.group,
            &right.normalized_name,
            &right.raw,
        ))
    });

    let workspace = parse_uv_workspace(target, path, &value)?;
    Ok((
        PythonProject {
            manifest_path: path.to_owned(),
            name,
            requires_python,
            backend,
            dependencies,
        },
        workspace,
    ))
}

fn parse_uv_workspace(
    target: &Path,
    path: &str,
    value: &toml::Value,
) -> Result<Option<WorkspaceEvidence>, String> {
    let Some(members) = value
        .get("tool")
        .and_then(toml::Value::as_table)
        .and_then(|tool| tool.get("uv"))
        .and_then(toml::Value::as_table)
        .and_then(|uv| uv.get("workspace"))
        .and_then(toml::Value::as_table)
        .and_then(|workspace| workspace.get("members"))
        .and_then(toml::Value::as_array)
    else {
        return Ok(None);
    };

    let patterns = members
        .iter()
        .filter_map(toml::Value::as_str)
        .map(ToOwned::to_owned)
        .collect::<Vec<_>>();
    let mut resolved = expand_workspace_members(target, path, &patterns)?;
    resolved.sort();
    resolved.dedup();
    Ok(Some(WorkspaceEvidence {
        kind: "uv".to_owned(),
        root: path.to_owned(),
        members: resolved,
    }))
}

fn expand_workspace_members(
    target: &Path,
    root_manifest: &str,
    patterns: &[String],
) -> Result<Vec<String>, String> {
    let root_dir = Path::new(root_manifest)
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."));
    let mut members = Vec::new();
    for pattern in patterns {
        let absolute_pattern = target.join(root_dir).join(pattern);
        if pattern.contains('*') {
            let Some(parent) = absolute_pattern.parent() else {
                continue;
            };
            let Some(file_name) = absolute_pattern.file_name().and_then(|name| name.to_str())
            else {
                continue;
            };
            let entries = std::fs::read_dir(parent).map_err(|error| {
                format!("cannot expand workspace member pattern {pattern}: {error}")
            })?;
            for entry in entries {
                let entry = entry.map_err(|error| error.to_string())?;
                if !entry.file_type().is_ok_and(|kind| kind.is_dir()) {
                    continue;
                }
                let name = entry.file_name();
                let Some(name) = name.to_str() else {
                    continue;
                };
                if !glob_match(file_name, name) {
                    continue;
                }
                let member_manifest = entry.path().join("pyproject.toml");
                if member_manifest.is_file() {
                    members.push(relative_path(target, &member_manifest));
                }
            }
        } else {
            let member_manifest = if absolute_pattern.file_name().and_then(|name| name.to_str())
                == Some("pyproject.toml")
            {
                absolute_pattern
            } else {
                absolute_pattern.join("pyproject.toml")
            };
            if member_manifest.is_file() {
                members.push(relative_path(target, &member_manifest));
            }
        }
    }
    Ok(members)
}

fn glob_match(pattern: &str, value: &str) -> bool {
    if let Some((prefix, suffix)) = pattern.split_once('*') {
        return value.starts_with(prefix)
            && value.ends_with(suffix)
            && value.len() >= prefix.len() + suffix.len();
    }
    pattern == value
}

fn poetry_python_constraint(value: &toml::Value) -> Option<String> {
    match value {
        toml::Value::String(raw) => Some(raw.clone()),
        toml::Value::Table(table) => table
            .get("version")
            .and_then(toml::Value::as_str)
            .map(ToOwned::to_owned),
        _ => None,
    }
}

fn parse_poetry_dependency_table(
    path: &str,
    group: &str,
    table: &toml::Table,
) -> Result<Vec<PythonRequirement>, String> {
    let mut requirements = Vec::new();
    for (name, value) in table {
        if name == "python" {
            continue;
        }
        let normalized = pep508_rs::PackageName::from_str(name)
            .map_err(|error| format!("invalid poetry package name {name}: {error}"))?
            .to_string();
        let constraint = match value {
            toml::Value::String(raw) => Some(raw.as_str()),
            toml::Value::Table(table) => table.get("version").and_then(toml::Value::as_str),
            _ => None,
        };
        let raw = match constraint {
            Some(constraint) => format!("{name} ({constraint})"),
            None => name.clone(),
        };
        requirements.push(PythonRequirement {
            raw,
            normalized_name: normalized,
            group: group.to_owned(),
            source: path.to_owned(),
        });
    }
    Ok(requirements)
}

fn parse_requirement_array(
    path: &str,
    group: &str,
    values: &[toml::Value],
) -> Result<Vec<PythonRequirement>, String> {
    values
        .iter()
        .map(|value| {
            let raw = value
                .as_str()
                .ok_or_else(|| "dependency must be a string".to_owned())?;
            parse_requirement(path, group, raw)
        })
        .collect()
}

fn parse_requirement(path: &str, group: &str, raw: &str) -> Result<PythonRequirement, String> {
    let requirement: Requirement = Requirement::from_str(raw).map_err(|error| error.to_string())?;
    Ok(PythonRequirement {
        raw: raw.to_owned(),
        normalized_name: requirement.name.to_string(),
        group: group.to_owned(),
        source: path.to_owned(),
    })
}

fn parse_requirements(
    path: &str,
    content: &str,
    warnings: &mut Vec<String>,
) -> Vec<PythonRequirement> {
    let mut requirements = Vec::new();
    for (index, line) in content.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if line.starts_with('-') {
            warnings.push(format!(
                "{path}:{}: requirements directive retained as unresolved evidence",
                index + 1
            ));
            continue;
        }
        match parse_requirement(path, "default", line) {
            Ok(requirement) => requirements.push(requirement),
            Err(error) => warnings.push(format!("{path}:{}: {error}", index + 1)),
        }
    }
    requirements
}

fn parse_toml_package_lock(path: &str, content: &str) -> Result<Vec<LockedPackage>, String> {
    let value: toml::Value = toml::from_str(content).map_err(|error| error.to_string())?;
    let packages = value
        .get("package")
        .and_then(toml::Value::as_array)
        .cloned()
        .unwrap_or_default();

    let mut locked = Vec::new();
    for package in packages {
        let Some(table) = package.as_table() else {
            return Err("lockfile package entry must be a table".to_owned());
        };
        let name = table
            .get("name")
            .and_then(toml::Value::as_str)
            .ok_or_else(|| "lockfile package is missing name".to_owned())?;
        let normalized = pep508_rs::PackageName::from_str(name)
            .map_err(|error| error.to_string())?
            .to_string();
        locked.push(LockedPackage {
            name: normalized,
            version: table
                .get("version")
                .and_then(toml::Value::as_str)
                .map(ToOwned::to_owned),
            source: path.to_owned(),
        });
    }
    locked.sort_by(|left, right| (&left.name, &left.version).cmp(&(&right.name, &right.version)));
    Ok(locked)
}

fn parse_conda_environment(path: &str, content: &str) -> Result<PythonProject, String> {
    let documents = YamlLoader::load_from_str(content).map_err(|error| error.to_string())?;
    let document = documents
        .first()
        .ok_or_else(|| "conda environment file is empty".to_owned())?;
    let name = document["name"].as_str().map(ToOwned::to_owned);

    let mut dependencies = Vec::new();
    let mut requires_python = None;
    if let Some(items) = document["dependencies"].as_vec() {
        for item in items {
            match item {
                Yaml::String(raw) => {
                    if let Some(python) = conda_python_constraint(raw) {
                        requires_python = Some(python);
                        continue;
                    }
                    if let Some(requirement) = conda_spec_requirement(path, "default", raw) {
                        dependencies.push(requirement);
                    }
                }
                Yaml::Hash(map) => {
                    for (key, value) in map {
                        if key.as_str() != Some("pip") {
                            continue;
                        }
                        let Some(pip_items) = value.as_vec() else {
                            continue;
                        };
                        for pip_item in pip_items {
                            let Some(raw) = pip_item.as_str() else {
                                continue;
                            };
                            match parse_requirement(path, "pip", raw) {
                                Ok(requirement) => dependencies.push(requirement),
                                Err(error) => {
                                    return Err(format!("pip dependency {raw}: {error}"));
                                }
                            }
                        }
                    }
                }
                _ => {}
            }
        }
    }

    dedupe_requirements(&mut dependencies);
    dependencies.sort_by(|left, right| {
        (&left.group, &left.normalized_name, &left.raw).cmp(&(
            &right.group,
            &right.normalized_name,
            &right.raw,
        ))
    });

    Ok(PythonProject {
        manifest_path: path.to_owned(),
        name,
        requires_python,
        backend: "conda".to_owned(),
        dependencies,
    })
}

fn conda_python_constraint(raw: &str) -> Option<String> {
    let trimmed = raw.trim();
    let rest = trimmed.strip_prefix("python")?;
    if rest.is_empty() {
        return Some("*".to_owned());
    }
    match rest.as_bytes().first() {
        Some(b'=') if rest.starts_with("==") => Some(rest.to_owned()),
        Some(b'=') => Some(format!("=={}", rest.trim_start_matches('='))),
        Some(b'<' | b'>' | b'!') => Some(rest.to_owned()),
        _ => None,
    }
}

fn conda_spec_requirement(path: &str, group: &str, raw: &str) -> Option<PythonRequirement> {
    let trimmed = raw.trim();
    if trimmed.is_empty() || trimmed.starts_with('#') {
        return None;
    }
    let name = trimmed.split(['=', '<', '>', '!', ' ', '|']).next()?.trim();
    if name.is_empty() || name == "python" {
        return None;
    }
    let normalized = pep508_rs::PackageName::from_str(name).ok()?.to_string();
    Some(PythonRequirement {
        raw: trimmed.to_owned(),
        normalized_name: normalized,
        group: group.to_owned(),
        source: path.to_owned(),
    })
}

fn parse_python_imports(path: &str, content: &str) -> Result<Vec<ImportEvidence>, String> {
    let mut parser = Parser::new();
    let language = tree_sitter_python::LANGUAGE.into();
    parser
        .set_language(&language)
        .map_err(|error| error.to_string())?;
    let tree = parser
        .parse(content, None)
        .ok_or_else(|| "Tree-sitter did not produce a syntax tree".to_owned())?;
    let mut imports = Vec::new();
    collect_imports(tree.root_node(), content.as_bytes(), path, &mut imports)?;
    Ok(imports)
}

fn collect_imports(
    node: Node<'_>,
    source: &[u8],
    path: &str,
    imports: &mut Vec<ImportEvidence>,
) -> Result<(), String> {
    let kind = node.kind();
    if kind == "import_statement" || kind == "import_from_statement" {
        let text = node.utf8_text(source).map_err(|error| error.to_string())?;
        for module in modules_from_import(kind, text) {
            imports.push(ImportEvidence {
                module,
                source_path: path.to_owned(),
                line: node.start_position().row + 1,
                kind: if kind == "import_from_statement" {
                    "fromImport"
                } else {
                    "import"
                }
                .to_owned(),
            });
        }
        return Ok(());
    }

    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        collect_imports(child, source, path, imports)?;
    }
    Ok(())
}

fn modules_from_import(kind: &str, text: &str) -> Vec<String> {
    let candidates: Vec<&str> = if kind == "import_from_statement" {
        text.strip_prefix("from ")
            .and_then(|rest| rest.split_once(" import "))
            .map_or_else(Vec::new, |(module, _)| vec![module])
    } else {
        text.strip_prefix("import ")
            .map_or_else(Vec::new, |rest| rest.split(',').collect())
    };

    candidates
        .into_iter()
        .filter_map(|candidate| {
            let module = candidate
                .split_whitespace()
                .next()?
                .trim_start_matches('.')
                .split('.')
                .next()?;
            (!module.is_empty()).then(|| module.to_owned())
        })
        .collect()
}

fn record_multi_project_workspace(snapshot: &mut DiscoverySnapshot) {
    let manifests = snapshot
        .projects
        .iter()
        .filter(|project| project.manifest_path.ends_with("pyproject.toml"))
        .map(|project| project.manifest_path.clone())
        .collect::<Vec<_>>();
    if manifests.len() < 2 {
        return;
    }
    if snapshot
        .workspaces
        .iter()
        .any(|workspace| workspace.kind == "uv" || workspace.kind == "multiProject")
    {
        return;
    }
    snapshot.workspaces.push(WorkspaceEvidence {
        kind: "multiProject".to_owned(),
        root: manifests[0].clone(),
        members: manifests,
    });
}

fn dedupe_requirements(requirements: &mut Vec<PythonRequirement>) {
    let mut seen = BTreeSet::new();
    requirements.retain(|item| {
        seen.insert((
            item.group.clone(),
            item.normalized_name.clone(),
            item.raw.clone(),
        ))
    });
}

fn sort_and_deduplicate(snapshot: &mut DiscoverySnapshot) {
    snapshot
        .manifests
        .sort_by(|left, right| left.path.cmp(&right.path));
    snapshot
        .lockfiles
        .sort_by(|left, right| left.path.cmp(&right.path));
    snapshot.workspaces.sort_by(|left, right| {
        (&left.kind, &left.root, &left.members).cmp(&(&right.kind, &right.root, &right.members))
    });
    snapshot
        .projects
        .sort_by(|left, right| left.manifest_path.cmp(&right.manifest_path));
    snapshot.imports.sort_by(|left, right| {
        (&left.module, &left.source_path, left.line).cmp(&(
            &right.module,
            &right.source_path,
            right.line,
        ))
    });
    let mut seen = BTreeSet::new();
    snapshot
        .imports
        .retain(|item| seen.insert((item.module.clone(), item.source_path.clone(), item.line)));
}

fn detect_python_tools(snapshot: &mut DiscoverySnapshot) {
    if !snapshot.projects.is_empty() || !snapshot.imports.is_empty() {
        snapshot.runtimes.push(tool_version("python3", "--version"));
    }
    if snapshot
        .lockfiles
        .iter()
        .any(|file| file.format == "uv.lock")
        || snapshot
            .workspaces
            .iter()
            .any(|workspace| workspace.kind == "uv")
    {
        snapshot
            .package_managers
            .push(tool_version("uv", "--version"));
    }
    if snapshot
        .lockfiles
        .iter()
        .any(|file| file.format == "poetry.lock")
        || snapshot
            .projects
            .iter()
            .any(|project| project.backend.contains("poetry"))
    {
        snapshot
            .package_managers
            .push(tool_version("poetry", "--version"));
    }
    if snapshot
        .projects
        .iter()
        .any(|project| project.backend == "conda")
        || snapshot
            .manifests
            .iter()
            .any(|file| file.format == "conda.environment")
    {
        snapshot
            .package_managers
            .push(tool_version("conda", "--version"));
    }
}

fn tool_version(name: &str, argument: &str) -> ToolEvidence {
    let version = probe_tool_version(name, argument);

    ToolEvidence {
        name: name.trim_end_matches('3').to_owned(),
        version,
        source: "hostPath".to_owned(),
    }
}

/// Probe a tool version with a two-second deadline and 8 KiB per-stream cap.
/// Unavailable, stalled, or unsuccessful tools have no detected version.
#[must_use]
pub fn probe_tool_version(name: &str, argument: &str) -> Option<String> {
    let mut child = Command::new(name)
        .arg(argument)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .ok()?;
    let deadline = Instant::now() + Duration::from_secs(2);
    let (sender, receiver) = std::sync::mpsc::channel();
    let stdout = child.stdout.take()?;
    let stderr = child.stderr.take()?;
    for (index, mut reader) in [
        (0, Box::new(stdout) as Box<dyn Read + Send>),
        (1, Box::new(stderr) as Box<dyn Read + Send>),
    ] {
        let sender = sender.clone();
        std::thread::spawn(move || {
            let mut bytes = Vec::new();
            let _ = reader.by_ref().take(8192).read_to_end(&mut bytes);
            let _ = sender.send((index, bytes));
        });
    }
    let success = loop {
        match child.try_wait() {
            Ok(Some(status)) => break status.success(),
            Ok(None) if Instant::now() < deadline => std::thread::sleep(Duration::from_millis(10)),
            _ => {
                let _ = child.kill();
                let _ = child.wait();
                return None;
            }
        }
    };
    if !success {
        return None;
    }
    let mut outputs = [Vec::new(), Vec::new()];
    for _ in 0..2 {
        let (index, bytes) = receiver
            .recv_timeout(deadline.saturating_duration_since(Instant::now()))
            .ok()?;
        outputs[index] = bytes;
    }
    let stdout = String::from_utf8_lossy(&outputs[0]);
    let stderr = String::from_utf8_lossy(&outputs[1]);
    let version = if stdout.trim().is_empty() {
        stderr.trim()
    } else {
        stdout.trim()
    };
    (!version.is_empty()).then(|| version.to_owned())
}
