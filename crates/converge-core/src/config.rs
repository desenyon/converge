//! Typed configuration resolution with field-level provenance.

use std::collections::BTreeMap;
use std::path::Path;

use converge_model::{Config, ConfigExplanation, NetworkPolicy, ResolvedSetting, SCHEMA_VERSION};

use crate::ConvergeError;

/// Highest-precedence CLI configuration values.
#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct ConfigOverrides {
    /// Network policy override.
    pub network: Option<NetworkPolicy>,
    /// Automatic-application override.
    pub auto_apply: Option<bool>,
    /// Telemetry override.
    pub telemetry: Option<bool>,
    /// Command timeout override.
    pub command_timeout_seconds: Option<u64>,
}

/// Resolve configuration in documented precedence order.
///
/// The `environment` map is injected to keep tests deterministic and avoid global environment
/// mutation. The optional user file normally points to `~/.config/converge/config.toml`.
///
/// # Errors
///
/// Returns an invalid-configuration error for malformed files or values.
pub fn resolve_config(
    target: &Path,
    user_config: Option<&Path>,
    environment: &BTreeMap<String, String>,
    cli: &ConfigOverrides,
) -> Result<ConfigExplanation, ConvergeError> {
    let mut config = Config::default();
    let mut sources = BTreeMap::from([
        ("network", "builtInDefaults"),
        ("autoApply", "builtInDefaults"),
        ("telemetry", "builtInDefaults"),
        ("commandTimeoutSeconds", "builtInDefaults"),
    ]);

    if let Some(path) = user_config.filter(|path| path.is_file()) {
        apply_file(path, None, "userConfig", &mut config, &mut sources)?;
    }
    let pyproject = target.join("pyproject.toml");
    if pyproject.is_file() {
        apply_file(
            &pyproject,
            Some(&["tool", "converge"]),
            "tool.converge",
            &mut config,
            &mut sources,
        )?;
    }
    let repository = target.join(".converge.toml");
    if repository.is_file() {
        apply_file(
            &repository,
            None,
            ".converge.toml",
            &mut config,
            &mut sources,
        )?;
    }
    apply_environment(environment, &mut config, &mut sources)?;
    apply_cli(cli, &mut config, &mut sources);

    if config.command_timeout_seconds == 0 {
        return Err(ConvergeError::InvalidInvocation(
            "commandTimeoutSeconds must be positive".to_owned(),
        ));
    }

    let settings = vec![
        ResolvedSetting {
            name: "network".to_owned(),
            value: match config.network {
                NetworkPolicy::Deny => "deny",
                NetworkPolicy::Allow => "allow",
            }
            .to_owned(),
            source: sources["network"].to_owned(),
        },
        ResolvedSetting {
            name: "autoApply".to_owned(),
            value: config.auto_apply.to_string(),
            source: sources["autoApply"].to_owned(),
        },
        ResolvedSetting {
            name: "telemetry".to_owned(),
            value: config.telemetry.to_string(),
            source: sources["telemetry"].to_owned(),
        },
        ResolvedSetting {
            name: "commandTimeoutSeconds".to_owned(),
            value: config.command_timeout_seconds.to_string(),
            source: sources["commandTimeoutSeconds"].to_owned(),
        },
    ];
    Ok(ConfigExplanation {
        schema_version: SCHEMA_VERSION.to_owned(),
        kind: "configExplanation".to_owned(),
        config,
        settings,
    })
}

fn apply_file(
    path: &Path,
    nested: Option<&[&str]>,
    source: &'static str,
    config: &mut Config,
    sources: &mut BTreeMap<&'static str, &'static str>,
) -> Result<(), ConvergeError> {
    let content = std::fs::read_to_string(path)
        .map_err(|error| ConvergeError::InvalidInvocation(error.to_string()))?;
    let mut value: toml::Value = toml::from_str(&content).map_err(|error| {
        ConvergeError::InvalidInvocation(format!("{}: {error}", path.display()))
    })?;
    if let Some(segments) = nested {
        for segment in segments {
            let Some(next) = value.get(*segment) else {
                return Ok(());
            };
            value = next.clone();
        }
    }
    apply_table(&value, source, config, sources)
}

fn apply_table(
    value: &toml::Value,
    source: &'static str,
    config: &mut Config,
    sources: &mut BTreeMap<&'static str, &'static str>,
) -> Result<(), ConvergeError> {
    let Some(table) = value.as_table() else {
        return Err(ConvergeError::InvalidInvocation(format!(
            "{source} configuration must be a TOML table"
        )));
    };
    for (name, value) in table {
        let valid = match name.as_str() {
            "network" => value.is_str(),
            "autoApply" | "telemetry" => value.is_bool(),
            "commandTimeoutSeconds" => value.is_integer(),
            _ => false,
        };
        if !valid {
            return Err(ConvergeError::InvalidInvocation(format!(
                "{source}: unknown setting or invalid type for {name}"
            )));
        }
    }
    if let Some(value) = table.get("network").and_then(toml::Value::as_str) {
        config.network = parse_network(value)?;
        sources.insert("network", source);
    }
    if let Some(value) = table.get("autoApply").and_then(toml::Value::as_bool) {
        config.auto_apply = value;
        sources.insert("autoApply", source);
    }
    if let Some(value) = table.get("telemetry").and_then(toml::Value::as_bool) {
        config.telemetry = value;
        sources.insert("telemetry", source);
    }
    if let Some(value) = table
        .get("commandTimeoutSeconds")
        .and_then(toml::Value::as_integer)
    {
        config.command_timeout_seconds = u64::try_from(value).map_err(|_| {
            ConvergeError::InvalidInvocation(
                "commandTimeoutSeconds must be a positive integer".to_owned(),
            )
        })?;
        if config.command_timeout_seconds == 0 {
            return Err(ConvergeError::InvalidInvocation(
                "commandTimeoutSeconds must be positive".to_owned(),
            ));
        }
        sources.insert("commandTimeoutSeconds", source);
    }
    Ok(())
}

fn apply_environment(
    environment: &BTreeMap<String, String>,
    config: &mut Config,
    sources: &mut BTreeMap<&'static str, &'static str>,
) -> Result<(), ConvergeError> {
    if let Some(value) = environment.get("CONVERGE_NETWORK") {
        config.network = parse_network(value)?;
        sources.insert("network", "environment");
    }
    if let Some(value) = environment.get("CONVERGE_AUTO_APPLY") {
        config.auto_apply = parse_bool("CONVERGE_AUTO_APPLY", value)?;
        sources.insert("autoApply", "environment");
    }
    if let Some(value) = environment.get("CONVERGE_TELEMETRY") {
        config.telemetry = parse_bool("CONVERGE_TELEMETRY", value)?;
        sources.insert("telemetry", "environment");
    }
    if let Some(value) = environment.get("CONVERGE_COMMAND_TIMEOUT_SECONDS") {
        config.command_timeout_seconds = value.parse().map_err(|_| {
            ConvergeError::InvalidInvocation(
                "CONVERGE_COMMAND_TIMEOUT_SECONDS must be a positive integer".to_owned(),
            )
        })?;
        if config.command_timeout_seconds == 0 {
            return Err(ConvergeError::InvalidInvocation(
                "CONVERGE_COMMAND_TIMEOUT_SECONDS must be positive".to_owned(),
            ));
        }
        sources.insert("commandTimeoutSeconds", "environment");
    }
    Ok(())
}

fn apply_cli(
    cli: &ConfigOverrides,
    config: &mut Config,
    sources: &mut BTreeMap<&'static str, &'static str>,
) {
    if let Some(value) = cli.network {
        config.network = value;
        sources.insert("network", "cli");
    }
    if let Some(value) = cli.auto_apply {
        config.auto_apply = value;
        sources.insert("autoApply", "cli");
    }
    if let Some(value) = cli.telemetry {
        config.telemetry = value;
        sources.insert("telemetry", "cli");
    }
    if let Some(value) = cli.command_timeout_seconds {
        config.command_timeout_seconds = value;
        sources.insert("commandTimeoutSeconds", "cli");
    }
}

fn parse_network(value: &str) -> Result<NetworkPolicy, ConvergeError> {
    match value {
        "deny" => Ok(NetworkPolicy::Deny),
        "allow" => Ok(NetworkPolicy::Allow),
        _ => Err(ConvergeError::InvalidInvocation(
            "network must be 'deny' or 'allow'".to_owned(),
        )),
    }
}

fn parse_bool(name: &str, value: &str) -> Result<bool, ConvergeError> {
    match value {
        "1" | "true" | "yes" => Ok(true),
        "0" | "false" | "no" => Ok(false),
        _ => Err(ConvergeError::InvalidInvocation(format!(
            "{name} must be true or false"
        ))),
    }
}
