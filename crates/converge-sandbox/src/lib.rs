//! Isolated validation backends.

use std::path::{Path, PathBuf};
use std::str::FromStr;

use converge_core::ConvergeError;
use converge_model::{
    Config, NetworkPolicy, RepairAction, RepairPlan, SCHEMA_VERSION, ToolInvocation,
    VerificationReport,
};
use tempfile::TempDir;
use toml_edit::{Array, DocumentMut, value};
use walkdir::WalkDir;

/// A temporary filesystem snapshot with proposed file changes applied.
pub struct PreparedSandbox {
    directory: TempDir,
    root: PathBuf,
}

/// A prepared sandbox retained together with its structured validation report.
pub struct ValidatedSandbox {
    sandbox: PreparedSandbox,
    report: VerificationReport,
}

impl ValidatedSandbox {
    /// Root containing the exact validated candidate files.
    #[must_use]
    pub fn root(&self) -> &Path {
        self.sandbox.root()
    }

    /// Structured verification result.
    #[must_use]
    pub const fn report(&self) -> &VerificationReport {
        &self.report
    }
}

impl PreparedSandbox {
    /// Copy a repository snapshot and apply typed file actions to the copy.
    ///
    /// # Errors
    ///
    /// Returns a validation error when source files cannot be copied or a typed edit cannot apply.
    pub fn create(target: &Path, plan: &RepairPlan) -> Result<Self, ConvergeError> {
        let directory =
            tempfile::tempdir().map_err(|error| ConvergeError::Validation(error.to_string()))?;
        let root = directory.path().join("repository");
        copy_repository(target, &root)?;
        if converge_discovery::discover(&root)?
            .repository
            .source_fingerprint
            != plan.source_fingerprint
        {
            return Err(ConvergeError::Validation(
                "copied repository fingerprint differs from the selected plan".to_owned(),
            ));
        }
        apply_file_actions(&root, plan)?;
        Ok(Self { directory, root })
    }

    /// Root of the isolated repository snapshot.
    #[must_use]
    pub fn root(&self) -> &Path {
        &self.root
    }

    /// Keep the temporary-directory owner observably live.
    #[must_use]
    pub fn storage_path(&self) -> &Path {
        self.directory.path()
    }
}

/// Apply and validate a plan entirely inside a temporary snapshot.
///
/// # Errors
///
/// Returns a validation error when the sandbox or an external-tool adapter cannot run.
pub async fn validate(
    target: &Path,
    plan: &RepairPlan,
    offline: bool,
) -> Result<VerificationReport, ConvergeError> {
    Ok(validate_prepared(target, plan, offline).await?.report)
}

/// Retain the exact validated sandbox for a later transactional apply.
///
/// # Errors
///
/// Returns a validation error when the sandbox or an external-tool adapter cannot run.
pub async fn validate_prepared(
    target: &Path,
    plan: &RepairPlan,
    offline: bool,
) -> Result<ValidatedSandbox, ConvergeError> {
    let config = Config {
        network: if offline {
            NetworkPolicy::Deny
        } else {
            NetworkPolicy::Allow
        },
        ..Config::default()
    };
    validate_prepared_with_config(target, plan, &config).await
}

/// Validate with the effective network and timeout policy, retaining the candidate files.
///
/// # Errors
/// Rejects an empty required contract and returns sandbox or subprocess failures.
pub async fn validate_prepared_with_config(
    target: &Path,
    plan: &RepairPlan,
    config: &Config,
) -> Result<ValidatedSandbox, ConvergeError> {
    if !plan
        .verification_contract
        .checks
        .iter()
        .any(|check| check.required)
    {
        return Err(ConvergeError::Validation(
            "no supported required verification contract; this target is discovery-only".to_owned(),
        ));
    }
    let sandbox = PreparedSandbox::create(target, plan)?;
    let mut invocations = vec![ToolInvocation {
        tool: "uv".to_owned(),
        arguments: vec!["--version".to_owned()],
        required: true,
        timeout_seconds: config.command_timeout_seconds,
    }];
    for action in &plan.actions {
        if let RepairAction::GenerateLockfile { tool, .. }
        | RepairAction::RefreshLockfile { tool, .. } = action
        {
            invocations.push(ToolInvocation {
                tool: tool.clone(),
                arguments: vec!["lock".to_owned()],
                required: true,
                timeout_seconds: config.command_timeout_seconds,
            });
        }
    }
    invocations.extend(plan.verification_contract.checks.clone());
    let mut checks = Vec::new();
    let mut passed = true;
    for mut invocation in invocations {
        invocation.timeout_seconds = config.command_timeout_seconds;
        let check = converge_executor::run_tool(
            &invocation,
            sandbox.root(),
            config.network == NetworkPolicy::Deny,
        )
        .await?;
        let failed = invocation.required && !check.passed;
        checks.push(check);
        if failed {
            passed = false;
            break;
        }
    }
    let report = VerificationReport {
        schema_version: SCHEMA_VERSION.to_owned(),
        kind: "verificationReport".to_owned(),
        plan_id: plan.plan_id.clone(),
        source_fingerprint: plan.source_fingerprint.clone(),
        network_allowed: config.network == NetworkPolicy::Allow,
        passed,
        checks,
    };
    Ok(ValidatedSandbox { sandbox, report })
}

fn copy_repository(source: &Path, destination: &Path) -> Result<(), ConvergeError> {
    std::fs::create_dir_all(destination)
        .map_err(|error| ConvergeError::Validation(error.to_string()))?;
    for entry in WalkDir::new(source)
        .follow_links(false)
        .into_iter()
        .filter_entry(|entry| {
            entry.depth() == 0
                || !entry.file_type().is_dir()
                || !matches!(
                    entry.file_name().to_str(),
                    Some(".git" | ".converge" | ".venv" | "target" | "node_modules")
                )
        })
    {
        let entry = entry.map_err(|error| ConvergeError::Validation(error.to_string()))?;
        let relative = entry
            .path()
            .strip_prefix(source)
            .map_err(|error| ConvergeError::Validation(error.to_string()))?;
        if relative.as_os_str().is_empty() {
            continue;
        }
        let output = destination.join(relative);
        if entry.file_type().is_symlink() {
            return Err(ConvergeError::Validation(format!(
                "filesystem-copy backend does not follow symlink: {}",
                entry.path().display()
            )));
        }
        if entry.file_type().is_dir() {
            std::fs::create_dir_all(&output)
                .map_err(|error| ConvergeError::Validation(error.to_string()))?;
        } else {
            if let Some(parent) = output.parent() {
                std::fs::create_dir_all(parent)
                    .map_err(|error| ConvergeError::Validation(error.to_string()))?;
            }
            std::fs::copy(entry.path(), &output)
                .map_err(|error| ConvergeError::Validation(error.to_string()))?;
        }
    }
    Ok(())
}

fn apply_file_actions(root: &Path, plan: &RepairPlan) -> Result<(), ConvergeError> {
    for action in &plan.actions {
        match action {
            RepairAction::AddDependency {
                manifest_path,
                distribution,
                group,
                ..
            } if group == "default" => {
                if manifest_path != "pyproject.toml" {
                    return Err(ConvergeError::Validation(
                        "only the root pyproject.toml is supported for mutation".to_owned(),
                    ));
                }
                add_project_dependency(&root.join(manifest_path), distribution)?;
            }
            RepairAction::AddDependency { group, .. } => {
                return Err(ConvergeError::Validation(format!(
                    "dependency group edits are not yet supported: {group}"
                )));
            }
            RepairAction::RemoveDependency { .. }
            | RepairAction::ChangeConstraint { .. }
            | RepairAction::SelectRuntime { .. } => {
                return Err(ConvergeError::Validation(format!(
                    "plan action is not supported by the sandbox adapter: {}",
                    action.id()
                )));
            }
            RepairAction::GenerateLockfile { .. }
            | RepairAction::RefreshLockfile { .. }
            | RepairAction::CreateEnvironment { .. }
            | RepairAction::NoChange { .. } => {}
        }
    }
    Ok(())
}

fn add_project_dependency(path: &Path, distribution: &str) -> Result<(), ConvergeError> {
    let content = std::fs::read_to_string(path)
        .map_err(|error| ConvergeError::Validation(format!("{}: {error}", path.display())))?;
    let mut document = DocumentMut::from_str(&content)
        .map_err(|error| ConvergeError::Validation(error.to_string()))?;
    let project = document
        .get_mut("project")
        .and_then(toml_edit::Item::as_table_like_mut)
        .ok_or_else(|| ConvergeError::Validation("[project] table is required".to_owned()))?;

    if project.get("dependencies").is_none() {
        project.insert("dependencies", value(Array::new()));
    }
    let dependencies = project
        .get_mut("dependencies")
        .and_then(toml_edit::Item::as_array_mut)
        .ok_or_else(|| {
            ConvergeError::Validation("project.dependencies must be an array".to_owned())
        })?;

    let already_declared = dependencies
        .iter()
        .filter_map(toml_edit::Value::as_str)
        .any(|requirement| {
            requirement
                .split(['<', '>', '=', '!', '~', '[', '@', ';'])
                .next()
                .is_some_and(|name| name.trim().eq_ignore_ascii_case(distribution))
        });
    if !already_declared {
        dependencies.push(distribution);
    }

    std::fs::write(path, document.to_string())
        .map_err(|error| ConvergeError::Validation(error.to_string()))
}
