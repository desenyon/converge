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
    /// Prohibit uv network access (also available through configuration).
    #[arg(long, global = true)]
    offline: bool,
    /// Maximum time in seconds for each external command.
    #[arg(long, global = true, value_parser = clap::value_parser!(u64).range(1..))]
    timeout: Option<u64>,
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
    let overrides = converge_core::ConfigOverrides {
        network: cli.offline.then_some(converge_model::NetworkPolicy::Deny),
        command_timeout_seconds: cli.timeout,
        ..Default::default()
    };
    match cli.command {
        Command::Discover(args) => {
            reject_sarif(&args)?;
            let snapshot = converge_discovery::discover(&args.path)?;
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
            let snapshot = converge_discovery::discover(&args.path)?;
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
            let snapshot = converge_discovery::discover(&args.path)?;
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
            let snapshot = converge_discovery::discover(&args.path)?;
            let diagnostics = converge_planner::diagnose(&snapshot);
            let config = effective_config(&args.path, &overrides)?;
            let plan = converge_planner::plan_with_config(&snapshot, &diagnostics, &config.config);
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
            let snapshot = converge_discovery::discover(&args.path)?;
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
            let config = effective_config(&args.path, &overrides)?;
            let plan = converge_planner::plan_with_config(&snapshot, &diagnostics, &config.config);
            let validated =
                converge_sandbox::validate_prepared_with_config(&args.path, &plan, &config.config)
                    .await?;
            let report = validated.report();
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
            let config = execution_config(&args.path, &overrides, args.yes)?;
            if !config.config.auto_apply {
                return Err(ConvergeError::InvalidInvocation(
                    "apply requires --yes after reviewing the plan identifier".to_owned(),
                ));
            }
            let snapshot = converge_discovery::discover(&args.path)?;
            let diagnostics = converge_planner::diagnose(&snapshot);
            let plan = converge_planner::plan_with_config(&snapshot, &diagnostics, &config.config);
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
            let (verification, receipt) = apply_workflow(&args.path, &plan, &config).await?;
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
            let (report, code) = solve_workflow(&args, &overrides).await?;
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
            let explanation = effective_config(&args.path, &overrides)?;
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
    overrides: &converge_core::ConfigOverrides,
) -> Result<(converge_model::SolveReport, u8), ConvergeError> {
    let discovery = converge_discovery::discover(&args.path)?;
    let diagnostics = converge_planner::diagnose(&discovery);
    let config = execution_config(&args.path, overrides, args.yes)?;
    let selected_plan =
        converge_planner::plan_with_config(&discovery, &diagnostics, &config.config);

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

    let reproduction = &mut report.reproduction[0].arguments;
    if config.config.network == converge_model::NetworkPolicy::Deny {
        reproduction.push("--offline".to_owned());
    }
    reproduction.extend([
        "--timeout".to_owned(),
        config.config.command_timeout_seconds.to_string(),
    ]);
    if args.frozen {
        reproduction.push("--frozen".to_owned());
    }
    if args.dry_run {
        return Ok((report, 0));
    }
    if requires_mutation(&report.selected_plan) && !args.yes && !config.config.auto_apply {
        return Ok((report, 1));
    }

    if requires_mutation(&report.selected_plan) {
        let (verification, receipt) =
            apply_workflow(&args.path, &report.selected_plan, &config).await?;
        report.verification = Some(verification);
        report.applied_changes = Some(receipt);
    } else {
        let verification = converge_sandbox::validate_prepared_with_config(
            &args.path,
            &report.selected_plan,
            &config.config,
        )
        .await?
        .report()
        .clone();
        let code = if verification.passed { 0 } else { 5 };
        report.verification = Some(verification);
        return Ok((report, code));
    }
    Ok((report, 0))
}

async fn apply_workflow(
    target: &std::path::Path,
    plan: &converge_model::RepairPlan,
    config: &converge_model::ConfigExplanation,
) -> Result<
    (
        converge_model::VerificationReport,
        converge_model::TransactionReceipt,
    ),
    ConvergeError,
> {
    let validated =
        converge_sandbox::validate_prepared_with_config(target, plan, &config.config).await?;
    let mut verification = validated.report().clone();
    if !verification.passed {
        let failed = verification.checks.iter().find(|check| !check.passed);
        return Err(ConvergeError::Validation(format!(
            "required sandbox check failed: {}",
            failed.map_or("no check result", |check| check.stderr.as_str())
        )));
    }
    let mut transaction = converge_executor::ApplicationTransaction::begin(
        target,
        validated.root(),
        plan,
        &verification,
    )?;
    match transaction.synchronize(plan, &config.config).await {
        Ok(checks) => verification.checks.extend(checks),
        Err(error) => return Err(transaction.rollback(&error)),
    }
    let receipt = transaction.commit(|receipt| {
        let final_snapshot = converge_discovery::discover(target)?;
        let graph = converge_graph::build_graph(&final_snapshot);
        let state = converge_store::Store::open(&target.join(".converge/state.db"))?;
        let audit = serde_json::to_string(&serde_json::json!({"receipt": receipt, "verification": verification, "configuration": config, "plan": plan, "sourceFingerprintAfter": graph.source_fingerprint}))
            .map_err(|error| ConvergeError::Invariant(error.to_string()))?;
        state.record_application(&graph, &format!("apply:{}", receipt.snapshot_path), &audit)
    })?;
    Ok((verification, receipt))
}

fn execution_config(
    target: &std::path::Path,
    overrides: &converge_core::ConfigOverrides,
    yes: bool,
) -> Result<converge_model::ConfigExplanation, ConvergeError> {
    let mut overrides = overrides.clone();
    if yes {
        overrides.auto_apply = Some(true);
    }
    effective_config(target, &overrides)
}

fn effective_config(
    target: &std::path::Path,
    overrides: &converge_core::ConfigOverrides,
) -> Result<converge_model::ConfigExplanation, ConvergeError> {
    let environment: BTreeMap<_, _> = std::env::vars()
        .filter(|(name, _)| name.starts_with("CONVERGE_"))
        .collect();
    let user = std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .map(|home| home.join(".config/converge/config.toml"));
    converge_core::resolve_config(target, user.as_deref(), &environment, overrides)
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
