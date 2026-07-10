#![allow(missing_docs)]

use std::collections::BTreeMap;

use converge_core::{ConfigOverrides, resolve_config};
use converge_model::NetworkPolicy;

#[test]
fn resolves_field_level_precedence_and_sources() {
    let target = tempfile::tempdir().expect("target");
    let user = target.path().join("user.toml");
    std::fs::write(
        &user,
        "network = \"deny\"\nautoApply = true\ncommandTimeoutSeconds = 10\n",
    )
    .expect("user config");
    std::fs::write(
        target.path().join("pyproject.toml"),
        "[tool.converge]\nnetwork = \"allow\"\ntelemetry = true\n",
    )
    .expect("pyproject");
    std::fs::write(
        target.path().join(".converge.toml"),
        "commandTimeoutSeconds = 20\n",
    )
    .expect("repo config");
    let environment = BTreeMap::from([("CONVERGE_AUTO_APPLY".to_owned(), "false".to_owned())]);
    let cli = ConfigOverrides {
        network: Some(NetworkPolicy::Deny),
        ..ConfigOverrides::default()
    };

    let explanation =
        resolve_config(target.path(), Some(&user), &environment, &cli).expect("config");
    assert_eq!(explanation.config.network, NetworkPolicy::Deny);
    assert!(!explanation.config.auto_apply);
    assert!(explanation.config.telemetry);
    assert_eq!(explanation.config.command_timeout_seconds, 20);
    assert_eq!(explanation.settings[0].source, "cli");
    assert_eq!(explanation.settings[1].source, "environment");
}
