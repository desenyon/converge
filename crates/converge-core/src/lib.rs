//! Use-case abstractions, policy, and error taxonomy.

use std::path::PathBuf;

use converge_model::DiscoverySnapshot;
use thiserror::Error;

mod config;

pub use config::{ConfigOverrides, resolve_config};

/// Stable application errors.
#[derive(Debug, Error)]
pub enum ConvergeError {
    /// The invocation or configuration is invalid.
    #[error("invalid invocation: {0}")]
    InvalidInvocation(String),
    /// Repository discovery failed.
    #[error("discovery failed: {0}")]
    Discovery(String),
    /// Hard constraints cannot be satisfied under the selected policy.
    #[error("unsatisfied constraints: {0}")]
    UnsatisfiedConstraints(String),
    /// Persistent local state failed.
    #[error("state storage failed: {0}")]
    Store(String),
    /// A required external tool is missing.
    #[error("required external tool unavailable: {0}")]
    ToolUnavailable(String),
    /// Isolated validation did not satisfy its required contract.
    #[error("validation failed: {0}")]
    Validation(String),
    /// Host mutation failed and repository files were restored.
    #[error("mutation failed; rollback completed: {0}")]
    MutationRolledBack(String),
    /// Rollback could not restore the prior repository state.
    #[error("rollback failed: {0}")]
    RollbackFailed(String),
    /// A Converge invariant was violated.
    #[error("internal invariant violated: {0}")]
    Invariant(String),
}

impl ConvergeError {
    /// Stable process exit code for this error.
    #[must_use]
    pub const fn exit_code(&self) -> u8 {
        match self {
            Self::InvalidInvocation(_) => 2,
            Self::Discovery(_) => 3,
            Self::UnsatisfiedConstraints(_) => 4,
            Self::Store(_) | Self::Invariant(_) => 10,
            Self::ToolUnavailable(_) => 8,
            Self::Validation(_) => 5,
            Self::MutationRolledBack(_) => 6,
            Self::RollbackFailed(_) => 7,
        }
    }
}

/// Repository-scoped discovery boundary.
pub trait DiscoveryService {
    /// Discover a repository without mutation.
    ///
    /// # Errors
    ///
    /// Returns a scoped discovery error when the target cannot be inspected.
    fn discover(&self, target: PathBuf) -> Result<DiscoverySnapshot, ConvergeError>;
}
