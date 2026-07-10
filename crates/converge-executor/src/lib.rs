//! Typed external-tool process adapters.

use std::path::Path;
use std::process::Command as StdCommand;
use std::time::Duration;

use converge_core::ConvergeError;
use converge_model::{CheckResult, ToolCapability, ToolInvocation};
use tokio::process::Command;

mod transaction;

pub use transaction::{
    TransactionStep, apply_validated, apply_validated_with_failure, synchronize_environment,
    undo_last,
};

/// Detect an external tool and record its exact version.
///
/// # Errors
///
/// Returns a tool-unavailable error when the executable is absent or rejects `--version`.
pub fn detect_tool(name: &str) -> Result<ToolCapability, ConvergeError> {
    if name != "uv" {
        return Err(ConvergeError::ToolUnavailable(format!(
            "unsupported adapter: {name}"
        )));
    }
    let output = StdCommand::new(name)
        .arg("--version")
        .output()
        .map_err(|error| ConvergeError::ToolUnavailable(format!("{name}: {error}")))?;
    if !output.status.success() {
        return Err(ConvergeError::ToolUnavailable(format!(
            "{name} --version exited with {}",
            output.status
        )));
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    let version = if stdout.trim().is_empty() {
        stderr.trim().to_owned()
    } else {
        stdout.trim().to_owned()
    };
    Ok(ToolCapability {
        name: name.to_owned(),
        version,
    })
}

/// Execute one typed validation invocation without a shell.
///
/// # Errors
///
/// Returns a validation error for an unsupported tool, spawn failure, or timeout.
pub async fn run_tool(
    invocation: &ToolInvocation,
    working_directory: &Path,
    offline: bool,
) -> Result<CheckResult, ConvergeError> {
    if invocation.tool != "uv" {
        return Err(ConvergeError::Validation(format!(
            "tool is not on the validation allowlist: {}",
            invocation.tool
        )));
    }

    let mut command = Command::new(&invocation.tool);
    command
        .args(&invocation.arguments)
        .current_dir(working_directory)
        .env("UV_NO_PROGRESS", "1")
        .env("UV_PYTHON_DOWNLOADS", "never")
        .kill_on_drop(true);
    if offline {
        command.env("UV_OFFLINE", "1");
    }

    let output = tokio::time::timeout(
        Duration::from_secs(invocation.timeout_seconds),
        command.output(),
    )
    .await
    .map_err(|_| {
        ConvergeError::Validation(format!(
            "{} timed out after {} seconds",
            invocation.tool, invocation.timeout_seconds
        ))
    })?
    .map_err(|error| ConvergeError::Validation(error.to_string()))?;

    Ok(CheckResult {
        tool: invocation.tool.clone(),
        arguments: invocation.arguments.clone(),
        exit_code: output.status.code(),
        passed: output.status.success(),
        stdout: redact_and_limit(&String::from_utf8_lossy(&output.stdout)),
        stderr: redact_and_limit(&String::from_utf8_lossy(&output.stderr)),
    })
}

fn redact_and_limit(value: &str) -> String {
    const LIMIT: usize = 65_536;
    let mut output = value
        .lines()
        .map(|line| {
            let uppercase = line.to_ascii_uppercase();
            if uppercase.contains("TOKEN=")
                || uppercase.contains("PASSWORD=")
                || uppercase.contains("API_KEY=")
            {
                "[REDACTED]"
            } else {
                line
            }
        })
        .collect::<Vec<_>>()
        .join("\n");
    output.truncate(output.floor_char_boundary(LIMIT.min(output.len())));
    output
}
