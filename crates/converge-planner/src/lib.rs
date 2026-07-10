//! Deterministic diagnosis, repair planning, and solver adapters.

use std::collections::{BTreeMap, BTreeSet};

use converge_model::{
    AlternativePlan, Confidence, Diagnostic, DiagnosticReport, DiagnosticType, DiscoverySnapshot,
    RepairAction, RepairPlan, SCHEMA_VERSION, Severity, ToolInvocation, VerificationContract,
};

/// Produce stable, evidence-backed diagnostics from normalized discovery evidence.
#[must_use]
pub fn diagnose(snapshot: &DiscoverySnapshot) -> DiagnosticReport {
    let declared: BTreeMap<_, _> = snapshot
        .projects
        .iter()
        .flat_map(|project| project.dependencies.iter())
        .map(|requirement| (requirement.normalized_name.as_str(), requirement))
        .collect();
    let imported_distributions: BTreeMap<_, _> = snapshot
        .imports
        .iter()
        .filter_map(|import| import_to_distribution(&import.module).map(|name| (name, import)))
        .collect();
    let imported_names: BTreeSet<_> = snapshot
        .imports
        .iter()
        .map(|import| normalize_module_name(&import.module))
        .collect();
    let locked: BTreeSet<_> = snapshot
        .locked_packages
        .iter()
        .map(|package| package.name.as_str())
        .collect();
    let mut diagnostics = Vec::new();

    for (distribution, import) in &imported_distributions {
        if !declared.contains_key(distribution) {
            diagnostics.push(Diagnostic {
                id: format!("python.missing-dependency:{distribution}"),
                diagnostic_type: DiagnosticType::MissingDependency,
                severity: Severity::Error,
                affected_entities: vec![
                    format!("module:{}", import.module),
                    format!("package:{distribution}"),
                ],
                evidence: vec![format!("{}:{}", import.source_path, import.line)],
                explanation: format!(
                    "Python imports module '{}' which maps to distribution '{distribution}', but no manifest declares it.",
                    import.module
                ),
                confidence: Confidence::High,
                possible_consequences: vec![
                    "environment import failure or undeclared transitive dependency".to_owned(),
                ],
                candidate_repair_actions: vec!["AddDependency".to_owned()],
                blocks_environment_creation: true,
            });
        }
    }

    for (distribution, requirement) in &declared {
        if requirement.group == "default"
            && !imported_distributions.contains_key(distribution)
            && !imported_names.contains(*distribution)
        {
            diagnostics.push(Diagnostic {
                id: format!("python.unused-dependency:{distribution}"),
                diagnostic_type: DiagnosticType::UnusedDependency,
                severity: Severity::Warning,
                affected_entities: vec![format!("package:{distribution}")],
                evidence: vec![requirement.source.clone()],
                explanation: format!(
                    "Distribution '{distribution}' is declared but has no mapped static import. Runtime or plugin use may still be valid."
                ),
                confidence: Confidence::Uncertain,
                possible_consequences: vec!["unnecessary install and supply-chain surface".to_owned()],
                candidate_repair_actions: vec!["NoChange".to_owned(), "RemoveDependency".to_owned()],
                blocks_environment_creation: false,
            });
        }

        if requirement.group == "default" && !locked.is_empty() && !locked.contains(distribution) {
            diagnostics.push(Diagnostic {
                id: format!("python.lock-drift:{distribution}"),
                diagnostic_type: DiagnosticType::LockDrift,
                severity: Severity::Error,
                affected_entities: vec![format!("package:{distribution}")],
                evidence: vec![requirement.source.clone()],
                explanation: format!(
                    "Distribution '{distribution}' is declared but absent from the parsed uv lockfile."
                ),
                confidence: Confidence::Certain,
                possible_consequences: vec!["frozen synchronization will reject the repository".to_owned()],
                candidate_repair_actions: vec!["RefreshLockfile".to_owned()],
                blocks_environment_creation: true,
            });
        }
    }

    diagnostics.sort_by(|left, right| left.id.cmp(&right.id));
    DiagnosticReport {
        schema_version: SCHEMA_VERSION.to_owned(),
        kind: "diagnosticReport".to_owned(),
        source_fingerprint: snapshot.repository.source_fingerprint.clone(),
        diagnostics,
    }
}

fn import_to_distribution(module: &str) -> Option<&'static str> {
    match module {
        "httpx" => Some("httpx"),
        "rich" => Some("rich"),
        "yaml" => Some("pyyaml"),
        "PIL" => Some("pillow"),
        "cv2" => Some("opencv-python"),
        "sklearn" => Some("scikit-learn"),
        "dateutil" => Some("python-dateutil"),
        _ => None,
    }
}

fn normalize_module_name(module: &str) -> String {
    module.to_ascii_lowercase().replace(['_', '.'], "-")
}

/// Create the minimal deterministic repair plan for a diagnostic report.
#[must_use]
#[allow(clippy::too_many_lines)]
pub fn plan(snapshot: &DiscoverySnapshot, report: &DiagnosticReport) -> RepairPlan {
    let manifest_path = snapshot.projects.first().map_or_else(
        || "pyproject.toml".to_owned(),
        |project| project.manifest_path.clone(),
    );
    let mut missing: Vec<_> = report
        .diagnostics
        .iter()
        .filter(|diagnostic| diagnostic.diagnostic_type == DiagnosticType::MissingDependency)
        .filter_map(|diagnostic| {
            diagnostic
                .id
                .rsplit_once(':')
                .map(|(_, name)| name.to_owned())
        })
        .collect();
    missing.sort();
    missing.dedup();

    let mut actions = Vec::new();
    let mut file_diff_preview = Vec::new();
    for distribution in &missing {
        actions.push(RepairAction::AddDependency {
            id: format!("add-dependency:{distribution}"),
            manifest_path: manifest_path.clone(),
            distribution: distribution.clone(),
            group: "default".to_owned(),
        });
        file_diff_preview.push(format!(
            "{manifest_path}: add project.dependencies entry {distribution:?}"
        ));
    }

    if !missing.is_empty() {
        if let Some(lockfile) = snapshot.lockfiles.first() {
            actions.push(RepairAction::RefreshLockfile {
                id: "refresh-lockfile:uv".to_owned(),
                lockfile_path: lockfile.path.clone(),
                tool: "uv".to_owned(),
            });
            file_diff_preview.push(format!("{}: refresh with uv", lockfile.path));
        } else {
            actions.push(RepairAction::GenerateLockfile {
                id: "generate-lockfile:uv".to_owned(),
                tool: "uv".to_owned(),
            });
            file_diff_preview.push("uv.lock: generate with uv".to_owned());
        }
    }

    if actions.is_empty() {
        actions.push(RepairAction::NoChange {
            id: "no-change".to_owned(),
            reason: "no deterministic blocking repair is required".to_owned(),
        });
    }

    let dependency_ordering = actions
        .last()
        .filter(|action| {
            matches!(
                action,
                RepairAction::GenerateLockfile { .. } | RepairAction::RefreshLockfile { .. }
            )
        })
        .map_or_else(Vec::new, |lock_action| {
            actions
                .iter()
                .filter(|action| matches!(action, RepairAction::AddDependency { .. }))
                .map(|action| (action.id().to_owned(), lock_action.id().to_owned()))
                .collect()
        });

    let checks = if missing.is_empty() && snapshot.lockfiles.is_empty() {
        Vec::new()
    } else {
        vec![
            ToolInvocation {
                tool: "uv".to_owned(),
                arguments: vec!["lock".to_owned(), "--check".to_owned()],
                required: true,
                timeout_seconds: 120,
            },
            ToolInvocation {
                tool: "uv".to_owned(),
                arguments: vec![
                    "sync".to_owned(),
                    "--frozen".to_owned(),
                    "--dry-run".to_owned(),
                ],
                required: true,
                timeout_seconds: 300,
            },
        ]
    };

    let mut id_hasher = blake3::Hasher::new();
    id_hasher.update(snapshot.repository.source_fingerprint.as_bytes());
    for action in &actions {
        id_hasher.update(action.id().as_bytes());
    }
    for (before, after) in &dependency_ordering {
        id_hasher.update(before.as_bytes());
        id_hasher.update(after.as_bytes());
    }
    let plan_id = format!("plan-{}", &id_hasher.finalize().to_hex()[..16]);

    RepairPlan {
        schema_version: SCHEMA_VERSION.to_owned(),
        kind: "repairPlan".to_owned(),
        plan_id,
        source_fingerprint: snapshot.repository.source_fingerprint.clone(),
        objective: if missing.is_empty() {
            "Preserve the verified repository state".to_owned()
        } else {
            "Declare imported Python distributions and establish a valid uv lock".to_owned()
        },
        actions,
        dependency_ordering,
        expected_result: "manifest declarations, lock state, and imported modules agree".to_owned(),
        assumptions: vec![
            "curated import-to-distribution mappings are correct for the cited modules".to_owned(),
        ],
        unresolved_uncertainty: snapshot.warnings.clone(),
        estimated_risk: if missing.is_empty() { "none" } else { "low" }.to_owned(),
        reversible: true,
        network_required: !missing.is_empty(),
        file_diff_preview,
        verification_contract: VerificationContract { checks },
        solver_explanation: vec![
            "satisfies blocking missing-dependency constraints".to_owned(),
            "adds only distributions supported by explicit import evidence".to_owned(),
            "keeps existing version intent and avoids major upgrades".to_owned(),
        ],
        alternatives: if missing.is_empty() {
            Vec::new()
        } else {
            vec![AlternativePlan {
                objective: "Remove imports from user source".to_owned(),
                rejection_reasons: vec![
                    "would alter user source intent and exceed dependency-repair scope".to_owned(),
                ],
            }]
        },
    }
}
