//! Local structured telemetry. Export is disabled by default.

/// Initialize local diagnostics without enabling network export.
pub fn init(quiet: bool) {
    if quiet {
        return;
    }
    let _ = tracing_subscriber::fmt()
        .with_target(false)
        .with_writer(std::io::stderr)
        .try_init();
}
