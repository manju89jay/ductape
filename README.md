# ductape

> The duct tape your data pipeline deserves.

**ductape** is a universal schema adapter generator. It parses versioned C struct
headers and generates compilable C++ converter code using a hub-and-spoke pattern
that scales linearly, not quadratically. Config-driven: YAML in, C++ out. Zero
manual converter code.

## Quick start

```bash
# Install
pip install -e .

# Generate adapters
ductape generate \
    --config variants/reference_project/config.yaml \
    --output build/

# Compile generated C++
g++ -c build/converters/generated/*.cpp \
    -Ibuild -Iruntime_reference -Ibuild/converters/generated -std=c++17

# Verify against golden files
ductape verify \
    --config variants/reference_project/config.yaml \
    --expected variants/reference_project/expected_output/
```

## How it works

Rather than generating converters between every pair of versions (N² problem),
ductape designates one **generic version** as a stable internal hub. Every
versioned struct converts to the generic version and optionally back.

```
V1 ──┐
V2 ──┼──► Generic (hub)  ──► V1, V2, V3 (reverse, optional)
V3 ──┘
```

This reduces the number of converters from N² to at most 2N per data type.

## Repository structure

```
ductape/
├── pyproject.toml                    Package metadata + CLI entry point
├── ductape/                          Python package
│   ├── __main__.py                   python -m ductape
│   ├── cli.py                        Argument parsing + dispatch
│   ├── config.py                     YAML config loader with validation
│   ├── codegen.py                    Generation driver
│   ├── warnings.py                   Diagnostic collector
│   └── conv/                         Core parsing + generation engine
│       ├── preprocessor.py           Comment stripping, #define capture
│       ├── expression_eval.py        Constant integer expression evaluator
│       ├── tokenizer.py              Lexer
│       ├── parser.py                 Recursive-descent C parser
│       ├── typecontainer.py          AST model (CType, CTypeMember)
│       ├── interface_version.py      Parse one header at one version
│       ├── type_registry.py          Collect types across all versions
│       ├── data_type.py              Logical type across versions
│       ├── data_type_version.py      One (type, version) tuple
│       ├── converter.py              Field-level C++ conversion generator
│       ├── code_writer.py            C++ file writer with indentation
│       ├── field_provenance.py       Cross-version field audit report
│       ├── source_container.py       Multi-source pointer manager
│       ├── value_container.py        Default value holder
│       └── pointers/                 Pointer abstractions
│           ├── struct_pointer.py     3-step fuzzy member lookup
│           ├── value_pointer.py      Default/override values
│           └── warning_null_pointer.py  Null-safe fallback
├── variants/reference_project/       Reference project configuration
│   ├── config.yaml                   Type registration, defaults, renames
│   ├── headers/                      Versioned C struct headers (v1/v2/v3)
│   └── expected_output/              Golden files for regression testing
├── runtime_reference/                Minimal adapter runtime headers
│   ├── adapter_base.h
│   └── version_info.h
├── tests/                            79 tests across 9 test files
└── docs/                             Documentation
    ├── architecture.md               Full specification (27 FRs, 16 sections)
    └── build-phases.md               Phased build plan
```

## Configuration

All project configuration lives in a single YAML file:

```yaml
project:
  name: reference_project
  generic_version_sentinel: 9999

header_sources:
  - path: "headers/v1"
    version_tag: "v1"
  - path: "headers/v2"
    version_tag: "v2"

types:
  TelemetryData_t:
    version_macro: TELEMETRY_DATA_VERSION
    generate_reverse: true
    defaults:
      battery.voltage: "0.0"
    renames:
      speed: ground_speed
      status: op_status
```

## Generated output

| File | Description |
|------|-------------|
| `data_types/<Type>.h` | All versions in C++ namespaces + generic superset |
| `converters/generated/Converter_<Type>.h` | Converter class declaration |
| `converters/generated/Converter_<Type>.cpp` | Field-by-field conversion implementations |
| `converters/generated/converters.cpp` | Factory registration function |
| `field_provenance.json` | Cross-version field audit report |

## Key features

- **Field-by-field copy** — no memcpy of whole structs, real field assignments
- **Rename handling** — `speed` in V1 → `ground_speed` in V3 via config
- **Array min-dimension copy** — `payload[32]` in V1 safely copies to `payload[64]` in V2
- **Default value injection** — missing fields get configurable defaults
- **Structural identity detection** — skips no-op converters (FR-08)
- **Semantic conflict detection** — warns when field types differ across versions
- **Field provenance report** — JSON audit trail for all field mappings

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Tech stack

- Python 3.10+, PyYAML, pytest
- Generated output: C++17 (compiles with g++)

## License

See repository for license information.
