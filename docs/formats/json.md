# JSON and SARIF

`--json` reserves standard output for one schema-versioned JSON document and suppresses local tracing. Output schemas are under `schemas/output`.

`check --sarif` and `diagnose --sarif` emit SARIF 2.1.0 with rule identifiers, severity, source file, line, confidence, and source fingerprint.

Schema changes require a version change or a compatibility-preserving addition plus schema tests.
