# ductape — Universal Schema Adapter Generator

## What this project is
A Python codegen tool that parses versioned C struct headers and generates
C++ converter code using a hub-and-spoke pattern. Config-driven: YAML in,
compilable C++ out. Zero manual converter code.

## Architecture reference
Read `ARCHITECTURE_FINAL_v3.md` for the full specification (27 FRs, 16 sections).
Read `docs/build-phases.md` for the phased build plan.

IMPORTANT: When starting any new phase, ALWAYS re-read `docs/build-phases.md`
to check which phase you're on and what the acceptance criteria are.

## Tech stack
- Python 3.10+, no deps beyond PyYAML and pytest
- Generated output is C++17, must compile with g++
- CLI entry point: `ductape` (via pyproject.toml)

## Repository structure
```
ductape/
├── pyproject.toml
├── ductape/                  # Python package
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── codegen.py
│   ├── warnings.py
│   └── conv/                 # Core parsing + generation engine
│       ├── preprocessor.py
│       ├── expression_eval.py
│       ├── tokenizer.py
│       ├── typecontainer.py
│       ├── parser.py
│       ├── interface_version.py
│       ├── type_registry.py
│       ├── data_type.py
│       ├── data_type_version.py
│       ├── converter.py
│       ├── code_writer.py
│       ├── source_container.py
│       ├── value_container.py
│       ├── field_provenance.py
│       └── pointers/
│           ├── struct_pointer.py
│           ├── value_pointer.py
│           └── warning_null_pointer.py
├── variants/reference_project/
│   ├── config.yaml
│   ├── headers/{v1,v2,v3}/telemetry_types.h
│   ├── headers/platform_types.h
│   └── expected_output/
├── runtime_reference/
│   ├── adapter_base.h
│   └── version_info.h
└── tests/
```

## Key commands
```bash
pip install -e .                    # Install in dev mode
pytest tests/ -v                    # Run all tests
ductape generate --config variants/reference_project/config.yaml --output build/
ductape verify --config variants/reference_project/config.yaml --expected variants/reference_project/expected_output/
g++ -c build/converters/generated/*.cpp -Ibuild/data_types -Iruntime_reference -std=c++17
```

## Code style
- Minimal: no over-engineering, no unnecessary abstractions
- Every module gets unit tests in tests/
- Generated C++ must be real compilable code, not pseudocode
- 2-space indentation in generated C++ (managed by CodeWriter)
- Use dataclasses where appropriate in Python

## IMPORTANT rules
- Build iteratively: get each phase working before starting the next
- Run tests after every phase — if a test fails, fix it before proceeding
- The hub-and-spoke pattern: every version converts to/from a generic hub version
- Generic version uses sentinel 9999 in C++, tagged GenericVersion type in Python
- When compacting, ALWAYS preserve: current phase number, which tests pass, which files exist
