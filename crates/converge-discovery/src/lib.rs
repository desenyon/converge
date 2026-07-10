//! Read-only repository and host discovery.

use std::collections::BTreeSet;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::str::FromStr;

use converge_core::ConvergeError;
use converge_model::{
    Confidence, DependencyFile, DiscoverySnapshot, Evidence, ImportEvidence, LockedPackage,
    PythonProject, PythonRequirement, ToolEvidence,
};
use pep508_rs::Requirement;
use time::OffsetDateTime;
use tree_sitter::{Node, Parser};
use uuid::Uuid;
use walkdir::WalkDir;

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
        let relative = relative_path(&target, path);
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
                match parse_pyproject(&relative, &content) {
                    Ok(project) => snapshot.projects.push(project),
                    Err(error) => snapshot.warnings.push(format!("{relative}: {error}")),
                }
            }
            Some("uv.lock") => {
                snapshot.lockfiles.push(DependencyFile {
                    path: relative.clone(),
                    format: "uv.lock".to_owned(),
                    fingerprint: content_fingerprint,
                });
                match parse_uv_lock(&relative, &content) {
                    Ok(packages) => snapshot.locked_packages.extend(packages),
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
                if let Some(project) = snapshot.projects.first_mut() {
                    project.dependencies.extend(requirements);
                } else {
                    snapshot.projects.push(PythonProject {
                        manifest_path: relative,
                        name: None,
                        requires_python: None,
                        dependencies: requirements,
                    });
                }
            }
            Some(_) if has_extension(path, "py") => {
                match parse_python_imports(&relative, &content) {
                    Ok(imports) => snapshot.imports.extend(imports),
                    Err(error) => snapshot.warnings.push(format!("{relative}: {error}")),
                }
            }
            _ => {}
        }
    }

    sort_and_deduplicate(&mut snapshot);
    detect_python_tools(&mut snapshot);
    Ok(snapshot)
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
    name == "pyproject.toml"
        || name == "uv.lock"
        || has_extension(path, "py")
        || is_requirements_file(name)
}

fn is_requirements_file(name: &str) -> bool {
    let extension = Path::new(name).extension().and_then(|value| value.to_str());
    (name.starts_with("requirements")
        && extension.is_some_and(|value| {
            value.eq_ignore_ascii_case("txt") || value.eq_ignore_ascii_case("in")
        }))
        || name == "constraints.txt"
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

fn parse_pyproject(path: &str, content: &str) -> Result<PythonProject, String> {
    let value: toml::Value = toml::from_str(content).map_err(|error| error.to_string())?;
    let project = value.get("project").and_then(toml::Value::as_table);
    let name = project
        .and_then(|table| table.get("name"))
        .and_then(toml::Value::as_str)
        .map(ToOwned::to_owned);
    let requires_python = project
        .and_then(|table| table.get("requires-python"))
        .and_then(toml::Value::as_str)
        .map(ToOwned::to_owned);

    let mut dependencies = Vec::new();
    if let Some(items) = project
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
        dependencies,
    })
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

fn parse_uv_lock(path: &str, content: &str) -> Result<Vec<LockedPackage>, String> {
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

fn sort_and_deduplicate(snapshot: &mut DiscoverySnapshot) {
    snapshot
        .manifests
        .sort_by(|left, right| left.path.cmp(&right.path));
    snapshot
        .lockfiles
        .sort_by(|left, right| left.path.cmp(&right.path));
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
    {
        snapshot
            .package_managers
            .push(tool_version("uv", "--version"));
    }
}

fn tool_version(name: &str, argument: &str) -> ToolEvidence {
    let version = Command::new(name)
        .arg(argument)
        .output()
        .ok()
        .filter(|output| output.status.success())
        .map(|output| {
            let stdout = String::from_utf8_lossy(&output.stdout);
            let stderr = String::from_utf8_lossy(&output.stderr);
            if stdout.trim().is_empty() {
                stderr.trim().to_owned()
            } else {
                stdout.trim().to_owned()
            }
        })
        .filter(|value| !value.is_empty());

    ToolEvidence {
        name: name.trim_end_matches('3').to_owned(),
        version,
        source: "hostPath".to_owned(),
    }
}
