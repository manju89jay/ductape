# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Migrated CI/CD from GitHub Actions to GitLab CI
- Added pre-push hook for local CI validation

## [0.1.0] - 2026-04-03

### Added
- **Core engine**: C header parser with preprocessor, tokenizer, and expression evaluator
- **Hub-and-spoke converters**: automatic to/from-generic conversion for every schema version
- **Config-driven codegen**: YAML config in, compilable C++17 out
- **CLI**: `ductape generate` and `ductape verify` commands
- **Plugin architecture**: pluggable parser frontends (C, Protobuf, JSON Schema) and code emitters (C++, Python, shared library)
- **Version negotiation**: runtime header and negotiation logic generation
- **Shared library emitter**: C ABI shared library with two-stage adaptation pipeline
- **Structural diff tool**: `ductape diff` for comparing schema versions
- **Field provenance**: JSON output tracking field origins across versions
- **Warning system**: configurable warnings for missing fields, type mismatches, and array truncation
- **Golden file verification**: `ductape verify` to validate generated output against expected baselines
- **Reference project**: complete multi-version telemetry example with expected output
- **179 tests** across 15 test modules covering all 35 architectural requirements
