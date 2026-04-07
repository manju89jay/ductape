# Contributing to ductape

Thanks for your interest in contributing! This guide will help you get started.

## Development Setup

```bash
# Clone the repository
git clone https://gitlab.com/manju89jay1/ductape.git
cd ductape

# Install in development mode
pip install -e ".[dev]"

# Install the pre-push hook
bash scripts/install-hooks.sh
```

Requires Python 3.10+ and g++ with C++17 support.

## Running Tests

```bash
pytest tests/ -v
```

All 179 tests must pass before pushing. The pre-push hook enforces this automatically.

## Full CI Pipeline (Local)

The pre-push hook runs the same checks as GitLab CI:

```bash
bash scripts/pre-push.sh
```

This runs: tests, adapter generation, C++ compilation, and golden file verification.

## Making Changes

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature main
   ```

2. Make your changes. Follow the existing code style:
   - Python: minimal abstractions, use dataclasses where appropriate
   - Generated C++: 2-space indentation (managed by `CodeWriter`)
   - Every module gets unit tests in `tests/`

3. Run the test suite and verify everything passes.

4. Commit with a clear message describing *why*, not just *what*.

5. Push and open a merge request against `main`.

## Project Architecture

Read `docs/architecture.md` for the full specification. Key concepts:

- **Hub-and-spoke pattern**: every schema version converts to/from a generic hub version
- **Config-driven**: YAML config defines types, versions, and header paths
- **Plugin system**: parser frontends (C, Protobuf, JSON Schema) and code emitters (C++, Python, shared lib)

## Reporting Issues

Open an issue on [GitLab](https://gitlab.com/manju89jay1/ductape/-/issues) with:
- What you expected vs. what happened
- Minimal reproduction steps
- Python version and OS

## Code of Conduct

Be respectful and constructive. We're all here to build good software.
