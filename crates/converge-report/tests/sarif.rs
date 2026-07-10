#![allow(missing_docs)]

use converge_model::{Confidence, Diagnostic, DiagnosticReport, DiagnosticType, Severity};
use converge_report::to_sarif;

#[test]
fn sarif_retains_rule_severity_and_source_location() {
    let report = DiagnosticReport {
        schema_version: "1.0.0".to_owned(),
        kind: "diagnosticReport".to_owned(),
        source_fingerprint: "abc".to_owned(),
        diagnostics: vec![Diagnostic {
            id: "python.missing-dependency:httpx".to_owned(),
            diagnostic_type: DiagnosticType::MissingDependency,
            severity: Severity::Error,
            affected_entities: vec!["package:httpx".to_owned()],
            evidence: vec!["src/app.py:4".to_owned()],
            explanation: "httpx is imported but undeclared".to_owned(),
            confidence: Confidence::High,
            possible_consequences: Vec::new(),
            candidate_repair_actions: vec!["AddDependency".to_owned()],
            blocks_environment_creation: true,
        }],
    };

    let sarif: serde_json::Value =
        serde_json::from_str(&to_sarif(&report).expect("SARIF")).expect("JSON");
    assert_eq!(sarif["version"], "2.1.0");
    assert_eq!(sarif["runs"][0]["results"][0]["level"], "error");
    assert_eq!(
        sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]["startLine"],
        4
    );
}
