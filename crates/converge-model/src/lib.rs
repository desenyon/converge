//! Stable, versioned Converge domain contracts.

use serde::{Deserialize, Serialize};
use time::OffsetDateTime;
use uuid::Uuid;

/// Current machine-readable schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Network access policy.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum NetworkPolicy {
    /// Prohibit network access.
    Deny,
    /// Permit recorded adapter network access.
    Allow,
}

/// Typed resolved application configuration.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Config {
    /// Network access policy.
    pub network: NetworkPolicy,
    /// Whether reviewed validated plans may auto-apply.
    pub auto_apply: bool,
    /// Whether telemetry export is opted in.
    pub telemetry: bool,
    /// Default external-command timeout.
    pub command_timeout_seconds: u64,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            network: NetworkPolicy::Allow,
            auto_apply: false,
            telemetry: false,
            command_timeout_seconds: 300,
        }
    }
}

/// One resolved configuration value and its winning source.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ResolvedSetting {
    /// Setting name.
    pub name: String,
    /// Serialized value.
    pub value: String,
    /// Winning precedence source.
    pub source: String,
}

/// Versioned configuration explanation.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConfigExplanation {
    /// Schema version.
    pub schema_version: String,
    /// Stable response kind.
    pub kind: String,
    /// Resolved typed configuration.
    pub config: Config,
    /// Setting-level provenance.
    pub settings: Vec<ResolvedSetting>,
}

/// Confidence attached to a piece of evidence.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum Confidence {
    /// Directly parsed or observed evidence.
    Certain,
    /// Strong inference from multiple signals.
    High,
    /// Incomplete or ambiguous inference.
    #[default]
    Uncertain,
}

/// Repository identity and state.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RepositoryIdentity {
    /// Canonical target path.
    pub target: String,
    /// Deterministic source-state fingerprint.
    pub source_fingerprint: String,
}

/// Host facts used during discovery.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct HostSnapshot {
    /// Operating system family.
    pub operating_system: String,
    /// CPU architecture.
    pub architecture: String,
}

/// An installed or repository-required runtime or package manager.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ToolEvidence {
    /// Canonical tool name.
    pub name: String,
    /// Detected version when available.
    pub version: Option<String>,
    /// Where the detection came from.
    pub source: String,
}

/// A manifest or lockfile observed in the repository.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DependencyFile {
    /// Repository-relative path.
    pub path: String,
    /// Ecosystem-specific format.
    pub format: String,
    /// Content fingerprint.
    pub fingerprint: String,
}

/// A normalized Python dependency declaration.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PythonRequirement {
    /// Original PEP 508 requirement.
    pub raw: String,
    /// PEP 503 normalized distribution name.
    pub normalized_name: String,
    /// Dependency group such as default or dev.
    pub group: String,
    /// Repository-relative evidence source.
    pub source: String,
}

/// A Python project declared by a manifest.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PythonProject {
    /// Repository-relative manifest path.
    pub manifest_path: String,
    /// Declared project name.
    pub name: Option<String>,
    /// Declared Python compatibility range.
    pub requires_python: Option<String>,
    /// Normalized dependency declarations.
    pub dependencies: Vec<PythonRequirement>,
}

/// A Python package resolved by a lockfile.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LockedPackage {
    /// Normalized distribution name.
    pub name: String,
    /// Exact resolved version when available.
    pub version: Option<String>,
    /// Repository-relative lockfile path.
    pub source: String,
}

/// A Python import extracted from a syntax tree.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ImportEvidence {
    /// Top-level imported module.
    pub module: String,
    /// Repository-relative source file.
    pub source_path: String,
    /// One-based source line.
    pub line: usize,
    /// Static import form.
    pub kind: String,
}

/// Stable graph node categories.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum NodeType {
    /// Repository root.
    Repository,
    /// Workspace boundary.
    Workspace,
    /// Project boundary.
    Project,
    /// Source or configuration file.
    File,
    /// Dependency manifest.
    Manifest,
    /// Dependency lockfile.
    Lockfile,
    /// Package identity.
    Package,
    /// Exact package version.
    PackageVersion,
    /// Imported module.
    Module,
    /// Language runtime.
    Runtime,
    /// Package manager or compiler.
    Toolchain,
    /// Repair plan.
    RepairPlan,
    /// Verification run.
    VerificationRun,
}

/// Stable graph edge categories.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum EdgeType {
    /// A manifest declares a package.
    Declares,
    /// A lockfile resolves a package version.
    ResolvesTo,
    /// Source imports a module.
    Imports,
    /// Hierarchical containment.
    Contains,
    /// A project requires a runtime or package.
    Requires,
    /// An entity conflicts with another.
    ConflictsWith,
    /// A newer observation replaces an older one.
    Supersedes,
    /// A package provides a module.
    Provides,
    /// Evidence was derived from another entity.
    DerivedFrom,
}

/// Persistable typed property-graph node.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GraphNode {
    /// Stable node identifier.
    pub id: String,
    /// Node category.
    pub node_type: NodeType,
    /// Source-state fingerprint.
    pub source_fingerprint: String,
}

impl GraphNode {
    /// Construct a graph node.
    #[must_use]
    pub fn new(id: impl Into<String>, node_type: NodeType, fingerprint: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            node_type,
            source_fingerprint: fingerprint.into(),
        }
    }
}

/// Persistable typed property-graph edge.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GraphEdge {
    /// Stable edge identifier.
    pub id: String,
    /// Source node identifier.
    pub source_id: String,
    /// Target node identifier.
    pub target_id: String,
    /// Edge category.
    pub edge_type: EdgeType,
    /// Evidence confidence.
    pub confidence: Confidence,
}

/// Versioned typed dependency graph output.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GraphSnapshot {
    /// Schema version.
    pub schema_version: String,
    /// Stable response kind.
    pub kind: String,
    /// Source repository fingerprint.
    pub source_fingerprint: String,
    /// Typed nodes in stable identifier order.
    pub nodes: Vec<GraphNode>,
    /// Typed edges in stable identifier order.
    pub edges: Vec<GraphEdge>,
}

/// Diagnostic severity.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum Severity {
    /// Informational observation.
    Info,
    /// Actionable but non-blocking risk.
    Warning,
    /// Environment creation cannot be trusted.
    Error,
}

/// Stable diagnostic categories.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum DiagnosticType {
    /// A mapped imported distribution is undeclared.
    MissingDependency,
    /// A declared distribution has no matching static import.
    UnusedDependency,
    /// Manifest requirements are absent from the lockfile.
    LockDrift,
    /// Declared Python ranges are incompatible.
    PythonVersionConflict,
    /// A local path dependency target is unavailable.
    LocalPathFailure,
    /// A native or system requirement may be missing.
    SystemRequirement,
}

/// Evidence-backed repository diagnostic.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Diagnostic {
    /// Stable diagnostic identifier.
    pub id: String,
    /// Stable diagnostic category.
    pub diagnostic_type: DiagnosticType,
    /// Severity.
    pub severity: Severity,
    /// Affected graph entity identifiers.
    pub affected_entities: Vec<String>,
    /// Raw evidence references.
    pub evidence: Vec<String>,
    /// Human-readable explanation.
    pub explanation: String,
    /// Confidence in the finding.
    pub confidence: Confidence,
    /// Possible consequences if unresolved.
    pub possible_consequences: Vec<String>,
    /// Typed repair action names that could address the finding.
    pub candidate_repair_actions: Vec<String>,
    /// Whether this finding blocks reproducible environment creation.
    pub blocks_environment_creation: bool,
}

/// Versioned diagnostic collection.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DiagnosticReport {
    /// Schema version.
    pub schema_version: String,
    /// Stable response kind.
    pub kind: String,
    /// Source repository fingerprint.
    pub source_fingerprint: String,
    /// Stable ordered findings.
    pub diagnostics: Vec<Diagnostic>,
}

/// A typed repository repair action.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(tag = "actionType", rename_all = "camelCase")]
pub enum RepairAction {
    /// Add a Python distribution to a manifest dependency array.
    AddDependency {
        /// Stable action identifier.
        id: String,
        /// Repository-relative target manifest.
        manifest_path: String,
        /// Normalized distribution name.
        distribution: String,
        /// Dependency group.
        group: String,
    },
    /// Remove a dependency declaration.
    RemoveDependency {
        /// Stable action identifier.
        id: String,
        /// Repository-relative target manifest.
        manifest_path: String,
        /// Normalized distribution name.
        distribution: String,
    },
    /// Change a version constraint.
    ChangeConstraint {
        /// Stable action identifier.
        id: String,
        /// Repository-relative target manifest.
        manifest_path: String,
        /// Normalized distribution name.
        distribution: String,
        /// Replacement constraint.
        constraint: String,
    },
    /// Select an already available runtime.
    SelectRuntime {
        /// Stable action identifier.
        id: String,
        /// Runtime request.
        requirement: String,
    },
    /// Generate a missing lockfile.
    GenerateLockfile {
        /// Stable action identifier.
        id: String,
        /// Ecosystem backend.
        tool: String,
    },
    /// Refresh a stale lockfile.
    RefreshLockfile {
        /// Stable action identifier.
        id: String,
        /// Repository-relative lockfile.
        lockfile_path: String,
        /// Ecosystem backend.
        tool: String,
    },
    /// Create the repository environment.
    CreateEnvironment {
        /// Stable action identifier.
        id: String,
        /// Environment backend.
        tool: String,
    },
    /// Explicitly preserve the current state.
    NoChange {
        /// Stable action identifier.
        id: String,
        /// Why no mutation is selected.
        reason: String,
    },
}

impl RepairAction {
    /// Stable action identifier.
    #[must_use]
    pub fn id(&self) -> &str {
        match self {
            Self::AddDependency { id, .. }
            | Self::RemoveDependency { id, .. }
            | Self::ChangeConstraint { id, .. }
            | Self::SelectRuntime { id, .. }
            | Self::GenerateLockfile { id, .. }
            | Self::RefreshLockfile { id, .. }
            | Self::CreateEnvironment { id, .. }
            | Self::NoChange { id, .. } => id,
        }
    }
}

/// Typed external command used only inside validation.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ToolInvocation {
    /// Adapter/tool name.
    pub tool: String,
    /// Individually escaped process arguments.
    pub arguments: Vec<String>,
    /// Whether this check must pass.
    pub required: bool,
    /// Timeout in seconds.
    pub timeout_seconds: u64,
}

/// Required validation stages for a repair plan.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VerificationContract {
    /// Environment and project checks in execution order.
    pub checks: Vec<ToolInvocation>,
}

/// Rejected candidate and rationale.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AlternativePlan {
    /// Candidate objective.
    pub objective: String,
    /// Why it ranked below the selected plan.
    pub rejection_reasons: Vec<String>,
}

/// Deterministic typed repair plan.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RepairPlan {
    /// Schema version.
    pub schema_version: String,
    /// Stable response kind.
    pub kind: String,
    /// Content-addressed plan identifier.
    pub plan_id: String,
    /// Source snapshot fingerprint.
    pub source_fingerprint: String,
    /// Human-readable objective.
    pub objective: String,
    /// Stable ordered typed actions.
    pub actions: Vec<RepairAction>,
    /// Action dependencies as pairs of action identifiers.
    pub dependency_ordering: Vec<(String, String)>,
    /// Expected resulting state.
    pub expected_result: String,
    /// Assumptions retained by the planner.
    pub assumptions: Vec<String>,
    /// Unresolved uncertainty.
    pub unresolved_uncertainty: Vec<String>,
    /// Risk class.
    pub estimated_risk: String,
    /// Whether all file actions can be undone from a snapshot.
    pub reversible: bool,
    /// Whether validation needs network access.
    pub network_required: bool,
    /// Human-readable unified-diff preview.
    pub file_diff_preview: Vec<String>,
    /// Required validation contract.
    pub verification_contract: VerificationContract,
    /// Transparent ranking rationale.
    pub solver_explanation: Vec<String>,
    /// Lower-ranked candidates.
    pub alternatives: Vec<AlternativePlan>,
}

/// Detected external-tool capability.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ToolCapability {
    /// Tool name.
    pub name: String,
    /// Exact version output.
    pub version: String,
}

/// Structured result of one validation command.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CheckResult {
    /// Adapter/tool name.
    pub tool: String,
    /// Individual process arguments.
    pub arguments: Vec<String>,
    /// Process exit code when available.
    pub exit_code: Option<i32>,
    /// Whether the check satisfied its contract.
    pub passed: bool,
    /// Redacted standard output.
    pub stdout: String,
    /// Redacted standard error.
    pub stderr: String,
}

/// Versioned isolated validation report.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VerificationReport {
    /// Schema version.
    pub schema_version: String,
    /// Stable response kind.
    pub kind: String,
    /// Plan identifier.
    pub plan_id: String,
    /// Source repository fingerprint.
    pub source_fingerprint: String,
    /// Whether validation was permitted to use the network.
    pub network_allowed: bool,
    /// Whether every required check passed.
    pub passed: bool,
    /// Structured command results.
    pub checks: Vec<CheckResult>,
}

/// File included in a host transaction.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppliedFile {
    /// Repository-relative path.
    pub path: String,
    /// Whether the file existed before application.
    pub existed_before: bool,
}

/// Structured result of an atomic host apply.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TransactionReceipt {
    /// Schema version.
    pub schema_version: String,
    /// Stable response kind.
    pub kind: String,
    /// Applied plan identifier.
    pub plan_id: String,
    /// Source fingerprint before application.
    pub source_fingerprint_before: String,
    /// Recoverable file records.
    pub files: Vec<AppliedFile>,
    /// Repository-relative snapshot location.
    pub snapshot_path: String,
}

/// Structured result of undoing the latest transaction.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UndoReceipt {
    /// Schema version.
    pub schema_version: String,
    /// Stable response kind.
    pub kind: String,
    /// Reverted plan identifier.
    pub plan_id: String,
    /// Restored files.
    pub files: Vec<AppliedFile>,
}

/// Complete result of the one-command solve state machine.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SolveReport {
    /// Schema version.
    pub schema_version: String,
    /// Stable response kind.
    pub kind: String,
    /// Discovery evidence.
    pub discovery: DiscoverySnapshot,
    /// Diagnostics considered by the planner.
    pub diagnostics: DiagnosticReport,
    /// Selected deterministic repair plan.
    pub selected_plan: RepairPlan,
    /// Isolated validation result when validation ran.
    pub verification: Option<VerificationReport>,
    /// Host transaction when application ran.
    pub applied_changes: Option<TransactionReceipt>,
    /// Exact typed reproduction invocations.
    pub reproduction: Vec<ToolInvocation>,
}

/// One persisted append-only audit record.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AuditRecord {
    /// Monotonic database sequence.
    pub sequence: i64,
    /// Stable event identifier.
    pub event_id: String,
    /// Redacted event JSON.
    pub event_json: String,
    /// UTC record time.
    pub recorded_at: String,
}

/// Versioned audit-log response.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AuditReport {
    /// Schema version.
    pub schema_version: String,
    /// Stable response kind.
    pub kind: String,
    /// Append-only records in sequence order.
    pub records: Vec<AuditRecord>,
}

impl GraphEdge {
    /// Construct a graph edge.
    #[must_use]
    pub fn new(
        id: impl Into<String>,
        source_id: impl Into<String>,
        target_id: impl Into<String>,
        edge_type: EdgeType,
        confidence: Confidence,
    ) -> Self {
        Self {
            id: id.into(),
            source_id: source_id.into(),
            target_id: target_id.into(),
            edge_type,
            confidence,
        }
    }
}

/// A raw observation supporting a conclusion.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Evidence {
    /// Stable evidence identifier.
    pub id: String,
    /// Evidence category.
    pub kind: String,
    /// Source path or command.
    pub source: String,
    /// Human-readable observation.
    pub observation: String,
    /// Confidence in this observation.
    pub confidence: Confidence,
}

/// Versioned read-only repository discovery result.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DiscoverySnapshot {
    /// Schema version.
    pub schema_version: String,
    /// Stable response kind.
    pub kind: String,
    /// Unique discovery run identifier.
    pub run_id: Uuid,
    /// UTC observation time.
    #[serde(with = "time::serde::rfc3339")]
    pub observed_at: OffsetDateTime,
    /// Repository identity.
    pub repository: RepositoryIdentity,
    /// Host facts.
    pub host: HostSnapshot,
    /// Detected runtimes.
    pub runtimes: Vec<ToolEvidence>,
    /// Detected package managers.
    pub package_managers: Vec<ToolEvidence>,
    /// Dependency manifests.
    pub manifests: Vec<DependencyFile>,
    /// Dependency lockfiles.
    pub lockfiles: Vec<DependencyFile>,
    /// Detected Python projects.
    pub projects: Vec<PythonProject>,
    /// Python source imports.
    pub imports: Vec<ImportEvidence>,
    /// Packages resolved by lockfiles.
    pub locked_packages: Vec<LockedPackage>,
    /// Supporting evidence.
    pub evidence: Vec<Evidence>,
    /// Non-fatal ambiguities.
    pub warnings: Vec<String>,
}

impl DiscoverySnapshot {
    /// Construct an empty snapshot for contract and adapter tests.
    #[must_use]
    pub fn empty(target: impl Into<String>) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.to_owned(),
            kind: "discoverySnapshot".to_owned(),
            run_id: Uuid::nil(),
            observed_at: OffsetDateTime::UNIX_EPOCH,
            repository: RepositoryIdentity {
                target: target.into(),
                source_fingerprint: String::new(),
            },
            host: HostSnapshot {
                operating_system: std::env::consts::OS.to_owned(),
                architecture: std::env::consts::ARCH.to_owned(),
            },
            runtimes: Vec::new(),
            package_managers: Vec::new(),
            manifests: Vec::new(),
            lockfiles: Vec::new(),
            projects: Vec::new(),
            imports: Vec::new(),
            locked_packages: Vec::new(),
            evidence: Vec::new(),
            warnings: Vec::new(),
        }
    }
}
