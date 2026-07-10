#![allow(missing_docs)]

use converge_executor::detect_tool;

#[test]
fn detects_uv_version_without_shell_interpolation() {
    let capability = detect_tool("uv").expect("uv installed for development");
    assert_eq!(capability.name, "uv");
    assert!(!capability.version.is_empty());
}
