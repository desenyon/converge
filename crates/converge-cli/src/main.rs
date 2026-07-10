//! Converge native command-line interface.

use std::collections::BTreeMap;
use std::path::PathBuf;
use std::process::ExitCode;

use clap::{Args, Parser, Subcommand};
use converge_core::ConvergeError;

#[derive(Debug, Parser)]
#[command(
    name = "converge",
    version,
    about = "Local-first dependency intelligence"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Discover repository and host evidence without mutation.
    Discover(TargetArgs),
    /// Check repository consistency without mutation.
    Check(TargetArgs),
    /// Show the typed dependency graph.
    Graph(TargetArgs),
    /// Diagnose repository inconsistencies.
    Diagnose(TargetArgs),
    /// Create a typed repair plan.
    Plan(TargetArgs),
    /// Explain evidence or a repair decision.
    Explain(TargetArgs),
    /// Validate the current project or a repair plan.
    Verify(TargetArgs),
    /// Apply an explicitly identified, freshly validated repair plan.
    Apply(ApplyArgs),
    /// Undo the latest successful host transaction.
    Undo(TargetArgs),
    /// Read the repository-local append-only audit log.
    Audit(TargetArgs),
    /// Discover, plan, validate, and optionally apply.
    Solve(SolveArgs),
    /// Show available external tools.
    Tools,
    /// Check host readiness.
    Doctor,
    /// Inspect typed configuration.
    Config(ConfigArgs),
}

#[derive(Debug, Args)]
struct ConfigArgs {
    #[command(subcommand)]
    command: ConfigCommand,
}

#[derive(Debug, Subcommand)]
enum ConfigCommand {
    /// Explain every resolved value and its winning source.
    Explain(TargetArgs),
}

#[derive(Debug, Args)]
struct TargetArgs {
    /// Repository directory to inspect.
    #[arg(default_value = ".")]
    path: PathBuf,
    /// Emit schema-versioned JSON only.
    #[arg(long)]
    json: bool,
    /// Emit SARIF 2.1.0 diagnostics only.
    #[arg(long, conflicts_with = "json")]
    sarif: bool,
}

#[derive(Debug, Args)]
#[allow(clippy::struct_excessive_bools)]
struct SolveArgs {
    /// Repository directory to solve.
    #[arg(default_value = ".")]
    path: PathBuf,
    /// Perform safe stages through plan generation only.
    #[arg(long)]
    dry_run: bool,
    /// Permit a validated plan to be applied noninteractively.
    #[arg(long)]
    yes: bool,
    /// Prohibit network access.
    #[arg(long)]
    offline: bool,
    /// Prohibit lockfile changes.
    #[arg(long)]
    frozen: bool,
    /// Emit schema-versioned JSON only.
    #[arg(long)]
    json: bool,
}

#[derive(Debug, Args)]
struct ApplyArgs {
    /// Repository directory containing the planned state.
    path: PathBuf,
    /// Exact plan identifier emitted by `converge plan`.
    plan_id: String,
    /// Confirm noninteractive host mutation.
    #[arg(long)]
    yes: bool,
    /// Prohibit network access.
    #[arg(long)]
    offline: bool,
    /// Emit schema-versioned JSON only.
    #[arg(long)]
    json: bool,
}

#[tokio::main]
async fn main() -> ExitCode {
    let cli = Cli::parse();
    let json_mode = matches!(
        &cli.command,
        Command::Discover(args)
            | Command::Check(args)
            | Command::Graph(args)
            | Command::Diagnose(args)
            | Command::Plan(args)
            | Command::Explain(args)
            | Command::Verify(args)
            | Command::Undo(args)
            | Command::Audit(args)
            if args.json || args.sarif
    ) || matches!(&cli.command, Command::Solve(args) if args.json)
        || matches!(&cli.command, Command::Apply(args) if args.json)
        || matches!(&cli.command, Command::Config(ConfigArgs { command: ConfigCommand::Explain(args) }) if args.json || args.sarif);

    converge_telemetry::init(json_mode);
    match run(cli).await {
        Ok(code) => ExitCode::from(code),
        Err(error) => {
            if json_mode {
                println!(
                    "{{\"schemaVersion\":\"1.0.0\",\"kind\":\"error\",\"message\":{}}}",
                    serde_json_escape(&error.to_string())
                );
            } else {
                eprintln!("{error}");
            }
            ExitCode::from(error.exit_code())
        }
    }
}

#[allow(clippy::too_many_lines)]
async fn run(cli: Cli) -> Result<u8, ConvergeError> {
    match cli.command {
        Command::Discover(args) => {
            reject_sarif(&args)?;
            let snapshot = converge_discovery::discover(args.path)?;
            if args.json {
                println!("{}", converge_report::to_json(&snapshot)?);
            } else {
                println!(
                    "Repository: {}\nFingerprint: {}\nEvidence: {}",
                    snapshot.repository.target,
                    snapshot.repository.source_fingerprint,
                    snapshot.evidence.len()
                );
            }
            Ok(0)
        }
        Command::Graph(args) => {
            reject_sarif(&args)?;
            let snapshot = converge_discovery::discover(args.path)?;
            let graph = converge_graph::build_graph(&snapshot);
            if args.json {
                println!("{}", converge_report::to_json(&graph)?);
            } else {
                println!(
                    "Graph: {} nodes, {} edges",
                    graph.nodes.len(),
                    graph.edges.len()
                );
            }
            Ok(0)
        }
        Command::Check(args) | Command::Diagnose(args) => {
            let snapshot = converge_discovery::discover(args.path)?;
            let report = converge_planner::diagnose(&snapshot);
            if args.json {
                println!("{}", converge_report::to_json(&report)?);
            } else if args.sarif {
                println!("{}", converge_report::to_sarif(&report)?);
            } else if report.diagnostics.is_empty() {
                println!("{}: no issues detected", snapshot.repository.target);
            } else {
                for diagnostic in &report.diagnostics {
                    println!(
                        "{:?} {}: {}",
                        diagnostic.severity, diagnostic.id, diagnostic.explanation
                    );
                }
            }
            Ok(u8::from(!report.diagnostics.is_empty()))
        }
        Command::Plan(args) => {
            reject_sarif(&args)?;
            let snapshot = converge_discovery::discover(args.path)?;
            let diagnostics = converge_planner::diagnose(&snapshot);
            let plan = converge_planner::plan(&snapshot, &diagnostics);
            if args.json {
                println!("{}", converge_report::to_json(&plan)?);
            } else {
                println!("Plan {}: {}", plan.plan_id, plan.objective);
                for action in &plan.actions {
                    println!("  {}", action.id());
                }
            }
            Ok(0)
        }
        Command::Explain(args) => {
            reject_sarif(&args)?;
            let snapshot = converge_discovery::discover(args.path)?;
            let report = converge_planner::diagnose(&snapshot);
            if args.json {
                println!("{}", converge_report::to_json(&report)?);
            } else if report.diagnostics.is_empty() {
                println!("No repair is required by deterministic diagnostics.");
            } else {
                for diagnostic in &report.diagnostics {
                    println!(
                        "{}\n  Evidence: {}",
                        diagnostic.explanation,
                        diagnostic.evidence.join(", ")
                    );
                }
            }
            Ok(0)
        }
        Command::Verify(args) => {
            reject_sarif(&args)?;
            let snapshot = converge_discovery::discover(&args.path)?;
            let diagnostics = converge_planner::diagnose(&snapshot);
            let plan = converge_planner::plan(&snapshot, &diagnostics);
            let report = converge_sandbox::validate(&args.path, &plan, false).await?;
            if args.json {
                println!("{}", converge_report::to_json(&report)?);
            } else {
                println!(
                    "Plan {} validation: {}",
                    plan.plan_id,
                    if report.passed { "passed" } else { "failed" }
                );
            }
            Ok(if report.passed { 0 } else { 5 })
        }
        Command::Apply(args) => {
            if !args.yes {
                return Err(ConvergeError::InvalidInvocation(
                    "apply requires --yes after reviewing the plan identifier".to_owned(),
                ));
            }
            let snapshot = converge_discovery::discover(&args.path)?;
            let diagnostics = converge_planner::diagnose(&snapshot);
            let plan = converge_planner::plan(&snapshot, &diagnostics);
            if plan.plan_id != args.plan_id {
                return Err(ConvergeError::Validation(format!(
                    "plan identifier does not match current repository state; expected {}",
                    plan.plan_id
                )));
            }
            if !requires_mutation(&plan) {
                return Err(ConvergeError::InvalidInvocation(
                    "selected plan contains no host mutation".to_owned(),
                ));
            }
            let (verification, receipt) = apply_workflow(&args.path, &plan, args.offline).await?;
            if args.json {
                println!("{}", converge_report::to_json(&receipt)?);
            } else {
                println!(
                    "Applied {} after {} passing checks. Undo with: converge undo {}",
                    receipt.plan_id,
                    verification.checks.len(),
                    args.path.display()
                );
            }
            Ok(0)
        }
        Command::Undo(args) => {
            reject_sarif(&args)?;
            let receipt = converge_executor::undo_last(&args.path)?;
            if args.json {
                println!("{}", converge_report::to_json(&receipt)?);
            } else {
                println!("Undid {} ({} files)", receipt.plan_id, receipt.files.len());
            }
            Ok(0)
        }
        Command::Audit(args) => {
            reject_sarif(&args)?;
            let report = converge_store::Store::read_audit(&args.path.join(".converge/state.db"))?;
            if args.json {
                println!("{}", converge_report::to_json(&report)?);
            } else if report.records.is_empty() {
                println!("No audit events recorded.");
            } else {
                for record in report.records {
                    println!("{} {}", record.recorded_at, record.event_id);
                }
            }
            Ok(0)
        }
        Command::Solve(args) => {
            let (report, code) = solve_workflow(&args).await?;
            if args.json {
                println!("{}", converge_report::to_json(&report)?);
            } else {
                print_solve_summary(&report, args.dry_run, args.yes);
            }
            Ok(code)
        }
        Command::Tools => {
            let uv = converge_executor::detect_tool("uv")?;
            println!("{}", uv.version);
            Ok(0)
        }
        Command::Doctor => {
            let uv = converge_executor::detect_tool("uv")?;
            println!("Converge host bootstrap is ready; {}", uv.version);
            Ok(0)
        }
        Command::Config(ConfigArgs {
            command: ConfigCommand::Explain(args),
        }) => {
            reject_sarif(&args)?;
            let environment: BTreeMap<_, _> = std::env::vars()
                .filter(|(name, _)| name.starts_with("CONVERGE_"))
                .collect();
            let user = std::env::var_os("HOME")
                .map(PathBuf::from)
                .map(|home| home.join(".config/converge/config.toml"));
            let explanation = converge_core::resolve_config(
                &args.path,
                user.as_deref(),
                &environment,
                &converge_core::ConfigOverrides::default(),
            )?;
            if args.json {
                println!("{}", converge_report::to_json(&explanation)?);
            } else {
                for setting in explanation.settings {
                    println!("{} = {} ({})", setting.name, setting.value, setting.source);
                }
            }
            Ok(0)
        }
    }
}

fn reject_sarif(args: &TargetArgs) -> Result<(), ConvergeError> {
    if args.sarif {
        Err(ConvergeError::InvalidInvocation(
            "--sarif is supported only by check and diagnose".to_owned(),
        ))
    } else {
        Ok(())
    }
}

async fn solve_workflow(
    args: &SolveArgs,
) -> Result<(converge_model::SolveReport, u8), ConvergeError> {
    let discovery = converge_discovery::discover(&args.path)?;
    let diagnostics = converge_planner::diagnose(&discovery);
    let selected_plan = converge_planner::plan(&discovery, &diagnostics);

    if args.frozen
        && selected_plan.actions.iter().any(|action| {
            matches!(
                action,
                converge_model::RepairAction::GenerateLockfile { .. }
                    | converge_model::RepairAction::RefreshLockfile { .. }
            )
        })
    {
        return Err(ConvergeError::UnsatisfiedConstraints(
            "--frozen prohibits the selected lockfile action".to_owned(),
        ));
    }

    let mut report = converge_model::SolveReport {
        schema_version: converge_model::SCHEMA_VERSION.to_owned(),
        kind: "solveReport".to_owned(),
        discovery,
        diagnostics,
        selected_plan,
        verification: None,
        applied_changes: None,
        reproduction: vec![converge_model::ToolInvocation {
            tool: "converge".to_owned(),
            arguments: vec![
                "solve".to_owned(),
                args.path.to_string_lossy().into_owned(),
                "--yes".to_owned(),
            ],
            required: true,
            timeout_seconds: 0,
        }],
    };

    if args.dry_run {
        return Ok((report, 0));
    }
    if requires_mutation(&report.selected_plan) && !args.yes {
        return Ok((report, 1));
    }

    if requires_mutation(&report.selected_plan) {
        let (verification, receipt) =
            apply_workflow(&args.path, &report.selected_plan, args.offline).await?;
        report.verification = Some(verification);
        report.applied_changes = Some(receipt);
    } else {
        let verification =
            converge_sandbox::validate(&args.path, &report.selected_plan, args.offline).await?;
        let code = if verification.passed { 0 } else { 5 };
        report.verification = Some(verification);
        return Ok((report, code));
    }
    Ok((report, 0))
}

async fn apply_workflow(
    target: &std::path::Path,
    plan: &converge_model::RepairPlan,
    offline: bool,
) -> Result<
    (
        converge_model::VerificationReport,
        converge_model::TransactionReceipt,
    ),
    ConvergeError,
> {
    let validated = converge_sandbox::validate_prepared(target, plan, offline).await?;
    let mut verification = validated.report().clone();
    if !verification.passed {
        return Err(ConvergeError::Validation(
            "one or more required sandbox checks failed".to_owned(),
        ));
    }
    let receipt =
        converge_executor::apply_validated(target, validated.root(), plan, &verification)?;

    let environment_check =
        match converge_executor::synchronize_environment(target, plan, offline).await {
            Ok(check) => check,
            Err(error) => return rollback_after_apply(target, &error),
        };
    verification.checks.push(environment_check);

    let final_snapshot = match converge_discovery::discover(target) {
        Ok(snapshot) => snapshot,
        Err(error) => return rollback_after_apply(target, &error),
    };
    let graph = converge_graph::build_graph(&final_snapshot);
    let state_path = target.join(".converge/state.db");
    let state = match converge_store::Store::open(&state_path) {
        Ok(state) => state,
        Err(error) => return rollback_after_apply(target, &error),
    };
    if let Err(error) = state.replace_graph(&graph.source_fingerprint, &graph.nodes, &graph.edges) {
        return rollback_after_apply(target, &error);
    }
    let audit = match serde_json::to_string(&(&receipt, &verification)) {
        Ok(audit) => audit,
        Err(error) => {
            let error = ConvergeError::Invariant(error.to_string());
            return rollback_after_apply(target, &error);
        }
    };
    if let Err(error) = state.append_audit_event(&format!("apply:{}", plan.plan_id), &audit) {
        return rollback_after_apply(target, &error);
    }
    Ok((verification, receipt))
}

fn rollback_after_apply<T>(
    target: &std::path::Path,
    cause: &ConvergeError,
) -> Result<T, ConvergeError> {
    match converge_executor::undo_last(target) {
        Ok(_) => Err(ConvergeError::MutationRolledBack(cause.to_string())),
        Err(rollback) => Err(ConvergeError::RollbackFailed(format!(
            "original error: {cause}; rollback error: {rollback}"
        ))),
    }
}

fn requires_mutation(plan: &converge_model::RepairPlan) -> bool {
    plan.actions
        .iter()
        .any(|action| !matches!(action, converge_model::RepairAction::NoChange { .. }))
}

fn print_solve_summary(report: &converge_model::SolveReport, dry_run: bool, yes: bool) {
    println!(
        "Plan {}: {}",
        report.selected_plan.plan_id, report.selected_plan.objective
    );
    for action in &report.selected_plan.actions {
        println!("  {}", action.id());
    }
    if dry_run {
        println!("Dry run complete; no host mutation occurred.");
    } else if let Some(receipt) = &report.applied_changes {
        println!(
            "Applied {} files after isolated validation. Undo with: converge undo {}",
            receipt.files.len(),
            report.discovery.repository.target
        );
    } else if requires_mutation(&report.selected_plan) && !yes {
        println!("Review the plan, then rerun with --yes to validate and apply it.");
    } else if report.verification.as_ref().is_some_and(|item| item.passed) {
        println!("Repository state passed isolated verification.");
    }
}

fn serde_json_escape(value: &str) -> String {
    serde_json::to_string(value).unwrap_or_else(|_| "\"serialization error\"".to_owned())
}
