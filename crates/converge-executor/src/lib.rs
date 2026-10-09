//! Typed external-tool process adapters.

use std::path::Path;
use std::process::Stdio;
use std::time::Duration;
use tokio::io::{AsyncRead, AsyncReadExt};

use converge_core::ConvergeError;
use converge_model::{CheckResult, ToolCapability, ToolInvocation};
use tokio::process::Command;

mod transaction;

pub use transaction::{
    ApplicationTransaction, TransactionStep, apply_validated, apply_validated_with_failure,
    synchronize_environment, undo_last,
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
    let version = converge_discovery::probe_tool_version(name, "--version").ok_or_else(|| {
        ConvergeError::ToolUnavailable(format!(
            "{name} --version failed or exceeded its two-second deadline"
        ))
    })?;
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

    let working_directory = working_directory
        .canonicalize()
        .map_err(|error| ConvergeError::Validation(error.to_string()))?;
    let mut command = Command::new(&invocation.tool);
    if offline {
        command.arg("--offline");
    }
    command
        .args(&invocation.arguments)
        .current_dir(&working_directory)
        .env("UV_NO_PROGRESS", "1")
        .env("UV_PYTHON_DOWNLOADS", "never")
        .env("UV_PROJECT_ENVIRONMENT", working_directory.join(".venv"))
        .env_remove("VIRTUAL_ENV")
        .env_remove("PYTHONPATH")
        .env_remove("PYTHONHOME")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);
    let mut child = command.spawn().map_err(|error| {
        if error.kind() == std::io::ErrorKind::NotFound {
            ConvergeError::ToolUnavailable(error.to_string())
        } else {
            ConvergeError::Validation(error.to_string())
        }
    })?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| ConvergeError::Invariant("missing stdout pipe".to_owned()))?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| ConvergeError::Invariant("missing stderr pipe".to_owned()))?;
    // Drain both streams concurrently, retaining bounded prefixes even for a noisy child.
    // Reader futures are scoped to the timeout, so inherited pipes cannot block forever.
    let result = tokio::time::timeout(Duration::from_secs(invocation.timeout_seconds), async {
        tokio::try_join!(child.wait(), capture(stdout), capture(stderr))
    })
    .await;
    let (status, stdout, stderr) = if let Ok(result) = result {
        result.map_err(|error| ConvergeError::Validation(error.to_string()))?
    } else {
        let _ = child.kill().await;
        let _ = child.wait().await;
        return Err(ConvergeError::Validation(format!(
            "{} timed out after {} seconds",
            invocation.tool, invocation.timeout_seconds
        )));
    };
    Ok(CheckResult {
        tool: invocation.tool.clone(),
        arguments: invocation.arguments.clone(),
        exit_code: status.code(),
        passed: status.success(),
        stdout,
        stderr,
    })
}

const OUTPUT_LIMIT: usize = 65_536;

async fn capture(mut reader: impl AsyncRead + Unpin) -> std::io::Result<String> {
    let mut bytes = Vec::new();
    let mut chunk = vec![0; 8192];
    let mut truncated = false;
    loop {
        let count = reader.read(&mut chunk).await?;
        if count == 0 {
            break;
        }
        let keep = count.min(OUTPUT_LIMIT.saturating_sub(bytes.len()));
        bytes.extend_from_slice(&chunk[..keep]);
        truncated |= keep < count;
    }
    // Drop the partial final line on truncation to avoid exposing a split secret key.
    if truncated {
        let end = bytes.iter().rposition(|byte| *byte == b'\n').unwrap_or(0);
        bytes.truncate(end);
    }
    let mut output = redact_and_limit(&String::from_utf8_lossy(&bytes));
    if truncated {
        output.push_str("\n[output truncated at 65536 bytes]");
    }
    Ok(output)
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

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn output_is_drained_but_retained_memory_is_bounded() {
        let bytes = vec![b'x'; OUTPUT_LIMIT * 20];
        let output = capture(bytes.as_slice()).await.unwrap();
        assert!(output.len() <= OUTPUT_LIMIT + 64);
        assert!(output.contains("truncated"));
    }

    #[tokio::test]
    async fn output_redacts_secrets_and_preserves_diagnostics() {
        let output = capture(b"diagnostic\nTOKEN=fake-test-value\nnext\n".as_slice())
            .await
            .unwrap();
        assert_eq!(output, "diagnostic\n[REDACTED]\nnext");
    }
}
