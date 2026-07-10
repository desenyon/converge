//! Stable human and machine-readable reporting.

use converge_core::ConvergeError;
use converge_model::{DiagnosticReport, Severity};
use serde::Serialize;

/// Serialize a versioned contract as compact JSON.
///
/// # Errors
///
/// Returns an invariant error when serialization unexpectedly fails.
pub fn to_json<T: Serialize>(value: &T) -> Result<String, ConvergeError> {
    serde_json::to_string(value).map_err(|error| ConvergeError::Invariant(error.to_string()))
}

/// Serialize diagnostics as SARIF 2.1.0.
///
/// # Errors
///
/// Returns an invariant error when serialization unexpectedly fails.
pub fn to_sarif(report: &DiagnosticReport) -> Result<String, ConvergeError> {
    let results: Vec<_> = report
        .diagnostics
        .iter()
        .map(|diagnostic| {
            let (path, line) = diagnostic
                .evidence
                .first()
                .map_or(("repository", 1), |evidence| parse_location(evidence));
            serde_json::json!({
                "ruleId": diagnostic.id,
                "level": match diagnostic.severity {
                    Severity::Error => "error",
                    Severity::Warning => "warning",
                    Severity::Info => "note",
                },
                "message": { "text": diagnostic.explanation },
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": { "uri": path },
                        "region": { "startLine": line }
                    }
                }],
                "properties": {
                    "confidence": format!("{:?}", diagnostic.confidence),
                    "sourceFingerprint": report.source_fingerprint
                }
            })
        })
        .collect();
    serde_json::to_string(&serde_json::json!({
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "Converge",
                    "version": env!("CARGO_PKG_VERSION"),
                    "informationUri": "https://github.com/concatenate-ai/converge"
                }
            },
            "results": results
        }]
    }))
    .map_err(|error| ConvergeError::Invariant(error.to_string()))
}

fn parse_location(evidence: &str) -> (&str, usize) {
    evidence
        .rsplit_once(':')
        .map_or((evidence, 1), |(path, line)| {
            (path, line.parse().unwrap_or(1))
        })
}
