# ductape — Universal Schema Adapter Generator

> Specification & Architecture

---

## 1. Problem Statement

### 1.1 The Schema Evolution Problem

In any system where multiple components exchange structured data, the schemas describing
that data evolve independently over time: fields are added, removed, renamed, or resized.
When a **producer** component and a **consumer** component operate against different versions
of the same schema, direct data exchange breaks — sizes differ, field offsets shift, and
unknown fields have no defined values.

This problem appears everywhere:
- **Embedded systems** exchange data through versioned C structs across firmware revisions
- **Microservice platforms** consume Protobuf or FlatBuffers messages that evolve across
  service releases
- **Data integration middleware** ingests feeds from dozens of sources, each with its own
  serialization format (binary structs, Protobuf, DDS IDL, JSON) and its own version cadence
- **IoT platforms** aggregate telemetry from heterogeneous devices running different firmware
- **Industrial control systems** bridge legacy serial protocols to modern message buses

The naive solution is to write a manual conversion function for every version pair of every
data type. This does not scale: with N data types each available in M versions, there are up
to N × M² converter functions to maintain. When data arrives in multiple serialization
formats, the combinatorics multiply further.

**This tool solves that problem through code generation.** Given:
- a set of schema definitions describing all known versions of every data type (C headers,
  `.proto` files, IDL files, JSON schemas, or any other supported format), and
- a configuration file that declares which types need adapters, specifies default values
  for new fields, and declares field renames between versions,

the tool automatically generates correct converter code — in C++, Python, Rust, or as
hot-reloadable shared libraries — that handles all known version and format combinations.
Maintainers only write configuration; they never write conversion code by hand.

### 1.2 The Multi-Source Ingestion Problem

A harder variant of the same problem arises in middleware and data platforms that ingest
data from **multiple sources using different serialization formats**. A platform might
simultaneously receive:
- Binary structs over shared memory from a co-located process
- Protobuf messages over gRPC from a remote service
- JSON payloads over REST from a third-party API
- Legacy binary frames over a serial bus from an older device

Each source speaks a different "language" (serialization format), and each language evolves
independently (schema versions). The platform needs two levels of adaptation:
1. **Intra-format adaptation:** Convert between versions within the same format
   (e.g., Protobuf schema V2 → V5)
2. **Cross-format normalization:** Convert from any format's canonical form into the
   platform's internal data model (e.g., Protobuf canonical → platform canonical)

Both levels are structurally identical field-mapping problems. This tool handles both
through the same hub-and-spoke engine, with pluggable parser frontends for each format.

### 1.3 Core Insight: Hub-and-Spoke Versioning

Rather than generating converters between every pair of versions (N² problem), the tool
designates one **generic version** as a stable internal hub. Every versioned schema converts
_to_ the generic version (and optionally _from_ the generic version back to any target
version). The runtime routes data through this hub.

```
        ┌──► V1
        │
Generic ├──► V2    (reverse: Generic → V_N, optional)
  (hub) ├──► V3
        │
V1 ──┐  │
V2 ──┼──► Generic  (forward: V_N → Generic, always generated)
V3 ──┘
V4 ──┘
```

This reduces the number of converters from N² to at most 2N per data type.

---

## 2. Scope

| In Scope | Out of Scope |
|---|---|
| Parsing versioned C struct headers | Executing the generated converter code |
| Parsing Protobuf `.proto` schema files | The adapter runtime framework itself |
| Parsing JSON Schema definitions | Full IDL compilers or code generators for RPC frameworks |
| Pluggable parser frontend architecture for additional formats | Manually handcrafted adapters for special cases |
| Generating versioned C++ namespace headers | Package creation or publishing |
| Generating converter classes (C++, Python, Rust, shared library) | CI pipeline library internals |
| Generating forward (V→Generic) and reverse (Generic→V) converters | Wire-format encoders/decoders (the tool generates schema adapters, not protocol parsers) |
| Two-stage adaptation: intra-format versioning + cross-format normalization | |
| Generating a converter factory registration function | |
| Hot-reloadable shared library output for runtime converter loading | |
| Dependency extraction from C/C++ package manager packages | |
| Standalone CLI invocation and optional CMake integration | |
| A reference project that validates the generator end-to-end | Production project variants (maintained in separate repos) |

---

## 3. Functional Specification

### 3.1 Functional Requirements

| ID | Requirement |
|---|---|
| FR-01 | The tool shall parse versioned C struct header files without requiring a full C++ compiler toolchain at generation time. A lightweight custom C parser with built-in constant-expression evaluation is sufficient. |
| FR-02 | The tool shall support multiple simultaneous versions of a data type by representing each as a distinct C++ namespace (`TypeName_V_<N>`). |
| FR-03 | A single **generic version** shall be generated for every data type, acting as a stable hub for all conversions. The generic version is identified by a tagged type in the Python model and a reserved sentinel integer in emitted C++ code. |
| FR-04 | For every (source version → generic version) pair, the tool shall generate a field-level C++ conversion function that copies matching fields by name. |
| FR-05 | Fields present in the generic version but absent from a source version shall be populated with configurable default values specified in the project configuration. |
| FR-06 | Array dimensions that differ between versions shall be handled by copying up to the minimum dimension size along each axis, without out-of-bounds access. |
| FR-07 | Field renames between versions (same data, different name) shall be expressible via rename directives in project configuration, without modifying the core engine. |
| FR-08 | The tool shall detect when a source and destination version are structurally identical and suppress generation of a no-op converter. |
| FR-09 | The tool shall emit a factory function that returns a registration list of all generated converter types, enabling dynamic loading by the runtime. |
| FR-10 | The tool shall extract header dependencies from C/C++ package manager packages and aggregate them into a flat, versioned folder structure for subsequent parsing. |
| FR-11 | The tool shall produce a CSV/JSON version overview listing each interface's active version number, usable for change-tracking and auditing. |
| FR-12 | When a previous version snapshot is supplied, the tool shall produce a diff report listing which interface version numbers changed between releases. |
| FR-13 | The tool shall warn — not fail — on missing source fields, grading warnings by configurable severity level. |
| FR-14 | The tool shall detect version conflicts (same version number, structurally different layouts) and raise an error. |
| FR-15 | The core generator engine shall be installable as a reusable Python package, consumable by other project repositories without copying source. |
| FR-16 | The tool shall optionally generate reverse converters (generic → specific version) when configured, enabling round-trip data flow to legacy consumers. |
| FR-17 | The built-in C parser shall evaluate constant integer expressions in `#define` macros and array dimensions (arithmetic operators, parentheses, previously-defined constants). |
| FR-18 | When the parser's fuzzy member lookup matches multiple candidates for a field name, it shall raise an ambiguity error rather than picking silently. |
| FR-19 | The parser shall handle C++ style struct declarations (`struct Name { ... };`), tagged typedefs (`typedef struct Tag { ... } Alias;`), anonymous struct/union members within parent structs, and forward declarations (`struct Foo;`). Unsupported constructs shall produce a warning, not a silent skip. |
| FR-20 | During the TypeRegistry merge phase, the tool shall perform field-type compatibility checks across versions. When the same field name appears with different C base types (e.g., `float32` in V1 vs `uint32` in V2), a warning shall be emitted. Optional `field_warnings` in config allow maintainers to document known semantic changes. |
| FR-21 | The tool shall emit a `field_provenance.json` report listing, for each field in the generic version, which source versions contribute that field, what C type it has in each version, and whether any configured field warnings apply. This enables auditing of semantic consistency across versions. |
| FR-22 | The parser layer shall be pluggable: new schema formats can be added by implementing a parser frontend that produces the shared `TypeContainer` intermediate representation, without modifying the core engine or any existing frontend. |
| FR-23 | The tool shall support Protobuf `.proto` files as an input format, parsing `message`, `enum`, `oneof`, and `map` declarations into the shared TypeContainer IR. Field numbers shall be tracked for compatibility analysis. |
| FR-24 | The tool shall support JSON Schema files as an input format, parsing `object` properties, `array` items, `$ref` references, and `enum` constraints into the shared TypeContainer IR. |
| FR-25 | The code emitter layer shall be pluggable: new output languages can be added by implementing an emitter backend that consumes the converter model, without modifying the core engine or any existing emitter. |
| FR-26 | The tool shall support emitting converters as shared libraries (`.so`/`.dll`) with a stable C ABI, enabling runtime hot-reload of adapters without process restart. A `GetConverterVersion()` symbol shall be exported for version negotiation. |
| FR-27 | The tool shall support two-stage adaptation pipelines: Stage 1 normalizes within a format family (e.g., Protobuf schema V2 → V5), Stage 2 normalizes across formats (e.g., Protobuf canonical → platform canonical). Both stages use the same hub-and-spoke engine and are configured in a single YAML file. |

### 3.2 Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | The generator shall run on Windows, Linux, and macOS without OS-specific logic in the core engine. |
| NFR-02 | The generator shall be invokable as a standalone CLI tool (`python -m ductape`). CMake integration is optional. |
| NFR-03 | Generated C++ code shall follow consistent indentation (configurable, default 2-space) managed by a dedicated code-writer utility class. |
| NFR-04 | The tool shall not require network access during the code-generation step itself; all dependencies must already be local. |
| NFR-05 | Warning and error output shall support coloured terminal output (ANSI codes) with a `--no-color` fallback. |
| NFR-06 | The tool shall be extensible to new project variants by adding a new `variants/<project>/` folder with configuration files, without modifying the core engine. |
| NFR-07 | All configuration files shall use YAML format with documented schema and validation at load time. Invalid config shall produce actionable error messages. |
| NFR-08 | The generator shall include a golden-file regression test mode (`--verify`) that compares generated output against checked-in reference output. |

### 3.3 Constraints & Assumptions

- Input headers contain `typedef struct` and `#define` version macros following the convention:
  `#define <TYPE>_VERSION <integer>`. The parser relies on this pairing. The parser also
  supports C++ style `struct Name { ... };`, tagged typedefs, anonymous struct/union members,
  and forward declarations (see FR-19). Unsupported constructs produce warnings, not silent skips.
- **Preprocessing strategy (pluggable):** By default, the built-in preprocessor handles
  comment stripping, `#define` capture, and `typedef` extraction. If headers use complex
  conditional compilation (`#ifdef`/`#ifndef` with non-trivial logic), an external
  preprocessor (gcc -E, clang -E, MSVC /EP) can be configured.
- Interface header packages are resolved by the package manager before generation.
  The generator itself does not perform package resolution.
- **Generic version sentinel:** In the Python model, the generic version is represented by a
  distinct `GenericVersion` tag (not an integer). In emitted C++ code, a configurable sentinel
  integer is used (default: 9999). A `static_assert` is emitted to guard against real version
  numbers colliding with the sentinel.
- **Semantic safety:** The generator performs field-type compatibility checks across versions
  (see FR-20) and emits `field_provenance.json` (see FR-21). These do not prevent generation;
  they ensure maintainers are aware of cross-version mismatches. For fields where the C type
  matches but the semantics differ, `field_warnings` in config.yaml provides a documentation
  mechanism.
- The generated C++ code depends on a small set of framework-provided headers
  (`adapter_base.h`, `version_info.h`). Minimal reference implementations of these headers
  are provided in the reference project.

---

## 4. System Context

```
 ┌─────────────────────────────────────────────────────────────────────┐
 │                     Developer / CI Pipeline                          │
 └───────────────┬────────────────────────────────────────┬────────────┘
                 │ CLI / cmake / build script              │ CI (Jenkins, GitLab, GH Actions)
                 ▼                                         ▼
  ┌──────────────────────────┐           ┌─────────────────────────────┐
  │   ductape     │           │   CI Pipeline Config         │
  │   (this repository)      │           │   (organisation-provided)    │
  └──────────────┬───────────┘           └─────────────────────────────┘
                 │ pip install / CMake find_package
                 ▼
  ┌──────────────────────────────────┐     ┌────────────────────────────┐
  │  C/C++ Package Manager Packages  │     │  Adapter Runtime Framework │
  │  (interface header packages)     │────▶│  AdapterConverterBase      │
  │  module_a_if, module_b_if, ...   │     │  IVersionInfo              │
  │  platform_types_pkg              │     │  Factory registration      │
  └──────────────────────────────────┘     └────────────────────────────┘
                 │ versioned C headers               ▲
                 ▼                                   │ loads at runtime
  ┌─────────────────────────────────────────────────┴──────────────────┐
  │   Generated Adapter C++ Code (OUTPUT)                               │
  │   data_types/TypeX.h  ·  Converter_TypeX.h/cpp  ·  converters.cpp  │
  └────────────────────────────────────────────────────────────────────┘
```

---

## 5. Recommended Repository Structure

```
ductape/
│
├── pyproject.toml                    Python package metadata + CLI entry point
├── CMakeLists.txt                    Optional CMake integration wrapper
├── README.md
│
├── ductape/                ◄── CORE REUSABLE ENGINE (Python package)
│   ├── __init__.py
│   ├── __main__.py                   CLI entry point: python -m ductape
│   ├── cli.py                        Argument parsing + dispatch
│   ├── config.py                     YAML config loader with schema validation
│   ├── codegen.py                    Generation driver — top-level orchestrator
│   ├── dependency_extractor.py       Gathers headers from packages; produces version CSVs
│   ├── version_diff.py              Compares two version snapshots
│   ├── warnings.py                   Centralised diagnostic collector (WarningModule)
│   │
│   ├── frontends/                    ◄── PARSER FRONTENDS (pluggable)
│   │   ├── __init__.py
│   │   ├── frontend_base.py          Abstract ParserFrontend interface
│   │   ├── c_header.py               C header parser (wraps conv/ pipeline)
│   │   ├── protobuf.py               Protobuf .proto parser → TypeContainer
│   │   └── json_schema.py            JSON Schema parser → TypeContainer
│   │
│   ├── emitters/                     ◄── CODE EMITTERS (pluggable)
│   │   ├── __init__.py
│   │   ├── emitter_base.py           Abstract CodeEmitter interface
│   │   ├── cpp_emitter.py            C++ class emitter (wraps existing CodeWriter)
│   │   ├── python_emitter.py         Python converter function emitter
│   │   ├── rust_emitter.py           Rust trait implementation emitter
│   │   └── shared_lib_emitter.py     Shared library (.so/.dll) emitter
│   │
│   └── conv/                         ◄── CORE ENGINE (format-agnostic, unchanged)
│       ├── __init__.py
│       ├── preprocessor.py           Built-in: strips comments, captures #defines
│       ├── expression_eval.py        Constant integer expression evaluator
│       ├── tokenizer.py              Lexer: classifies text into typed tokens
│       ├── parser.py                 Recursive-descent C parser → TypeContainer
│       ├── typecontainer.py          AST-like model: types, defines, namespaces
│       ├── interface_version.py      One header package at one version → TypeContainer
│       ├── type_registry.py          Registry + orchestrator: drives generation steps
│       ├── data_type.py              One logical type across all its versions
│       ├── data_type_version.py      One (type, version) tuple with struct layout
│       ├── converter.py              Generates field-level conversion function bodies
│       ├── code_writer.py            Low-level file writer with indentation tracking
│       ├── source_container.py       Multi-source pointer manager for tree-walking
│       ├── value_container.py        Default / override value holder
│       ├── field_provenance.py       Cross-version field audit + provenance report
│       └── pointers/
│           ├── __init__.py
│           ├── struct_pointer.py         Navigates into versioned struct members
│           ├── named_source_pointer.py   Rename/alias pointer
│           ├── value_pointer.py          Default/override value pointer
│           ├── call_pointer.py           Runtime-dispatch for custom conversions
│           └── warning_null_pointer.py   Null-safe fallback with diagnostics
│
├── variants/                         ◄── PROJECT-VARIANT CONFIGURATIONS
│   ├── reference_c_structs/          Reference project: C header → C++ converters
│   │   ├── config.yaml
│   │   ├── headers/
│   │   │   ├── platform_types.h
│   │   │   ├── v1/telemetry_types.h
│   │   │   ├── v2/telemetry_types.h
│   │   │   └── v3/telemetry_types.h
│   │   ├── defaults/
│   │   │   ├── __init__.py
│   │   │   ├── gen_base.py
│   │   │   └── gen_telemetry.py
│   │   └── expected_output/
│   │       ├── data_types/
│   │       ├── converters/
│   │       └── field_provenance.json
│   │
│   └── reference_multi_format/       Reference project: Protobuf + C → two-stage
│       ├── config.yaml               Multi-source config with stage1 + stage2
│       ├── schemas/
│       │   ├── telemetry_v1.proto
│       │   ├── telemetry_v2.proto
│       │   └── canonical_types.h
│       └── expected_output/
│           ├── converters/
│           └── field_provenance.json
│
├── runtime_reference/                ◄── MINIMAL ADAPTER RUNTIME (for testing)
│   ├── adapter_base.h                Minimal AdapterConverterBase definition
│   └── version_info.h                Minimal IVersionInfo definition
│
└── tests/
    ├── test_preprocessor.py
    ├── test_tokenizer.py
    ├── test_parser.py
    ├── test_expression_eval.py
    ├── test_converter_generation.py
    ├── test_config_validation.py
    ├── test_semantic_conflicts.py    Field-type compat, field_warnings, provenance
    ├── test_ambiguity_detection.py   Fuzzy lookup with multiple candidates
    ├── test_protobuf_frontend.py     Protobuf .proto parsing → TypeContainer
    ├── test_json_schema_frontend.py  JSON Schema parsing → TypeContainer
    ├── test_python_emitter.py        Python converter output correctness
    ├── test_two_stage_pipeline.py    End-to-end multi-format two-stage test
    └── test_golden_files.py          Regression: compare output vs expected_output/
```

---

## 6. Detailed Architecture

### 6.1 Layered Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 6: CI / Build Infrastructure                                  │
│  CI config · optional CMakeLists.txt · pyproject.toml                │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 5: CLI / Orchestration                                        │
│  cli.py  ·  config.py (YAML + validation)                            │
│  · Standalone: python -m ductape --config config.yaml      │
│  · Optional:   CMake add_custom_target wrapper                       │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 4: Entry-Point Scripts                                        │
│  dependency_extractor.py    codegen.py    version_diff.py            │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 3a: Parser Frontends (pluggable)  Layer 3b: Code Emitters     │
│  frontends/                              emitters/                   │
│  · c_header.py  (existing)               · cpp_emitter.py (existing) │
│  · protobuf.py  (new)                    · python_emitter.py (new)   │
│  · json_schema.py (new)                  · rust_emitter.py (new)     │
│  · [future: idl, avro, ...]              · shared_lib_emitter.py     │
│       │                                         ▲                    │
│       ▼                                         │                    │
│  ┌─────────── TypeContainer IR ─────────────────┘                    │
│  │            (format-agnostic shared representation)                 │
├──┴──────────────────────────────────────────────────────────────────┤
│  Layer 2a: Core Generator Engine         Layer 2b: Project Variant   │
│  conv/ sub-package (UNCHANGED)           variants/<project>/         │
│  · ExprEval · TypeRegistry              · config.yaml               │
│  · DataType / DataTypeVersion           · defaults/gen_*.py         │
│  · Converter · SourceContainer                                       │
│  · FieldProvenance · SemanticCheck                                   │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 1: Pointer Abstractions (UNCHANGED)                           │
│  StructPointer · NamedSourcePointer · ValuePointer · CallPointer     │
│  WarningNullPointer                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Build & CI Layer

| Artifact | Purpose |
|---|---|
| `pyproject.toml` | Python package metadata. Declares `ductape` as an installable package with a CLI entry point (`ductape` command). |
| `CMakeLists.txt` | **(Optional)** Thin wrapper that locates `Python3`, resolves C/C++ packages via `find_package()`, writes a `resolved_paths.yaml`, and invokes the CLI. Projects that don't use CMake invoke the CLI directly. |
| CI config | Minimal CI entry point. Runs `pip install -e .`, then `ductape --config variants/<project>/config.yaml --verify` for regression, and `--generate` for output. |

### 6.3 CLI / Orchestration Layer

The core engine is invoked as a **standalone CLI tool**:

```bash
# Install
pip install -e .

# Generate adapters
ductape generate \
    --config variants/reference_project/config.yaml \
    --output build/generated/

# Verify against golden files (CI regression check)
ductape verify \
    --config variants/reference_project/config.yaml \
    --expected variants/reference_project/expected_output/

# Extract dependencies (when using package manager packages)
ductape extract-deps \
    --config variants/reference_project/config.yaml \
    --output build/interfaces/

# Diff two version snapshots
ductape diff \
    --current build/interfaces/v2.0/ \
    --previous build/interfaces/v1.0/
```

**CMake integration (optional):** For projects that use CMake, a thin wrapper invokes the
CLI as custom targets:

```cmake
find_package(Python3 REQUIRED Interpreter)

add_custom_target(ADAPTER_GENERATE ALL
    COMMAND ${Python3_EXECUTABLE} -m ductape generate
            --config ${CMAKE_CURRENT_SOURCE_DIR}/config.yaml
            --output ${CMAKE_CURRENT_BINARY_DIR}/generated/
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
)
```

### 6.4 Core Generator Engine

#### 6.4.1 `dependency_extractor.py` — Header Aggregator

**Role:** Gathers all scattered per-package header files into a structured directory
that can be consumed by the parser.

**Design note:** Rather than concatenating all packages into mega-files (which
causes name collisions), each package is parsed independently. Cross-package type
conflicts are detected during the TypeRegistry merge phase.

**Inputs:**
- `config.yaml` → `header_sources` section
- `--current-version` tag
- `--previous-version` tag (optional)

**Algorithm:**

1. For each header source in config:
   - Copy headers into `interfaces/<version>/<source_tag>/`
   - Scan for version `#define` lines
2. Parse version macros and cross-reference with `types` in config → write
   `interfaces/<version>/version_overview.json`
3. If `--previous-version` supplied: compute diff → write `version_diff.json`

**Outputs:**
- `interfaces/<version>/` — organised headers ready for parsing (per-package, not merged)
- `interfaces/<version>/version_overview.json` — active version numbers per type
- `interfaces/<version>/version_diff.json` — delta (optional)

#### 6.4.2 `codegen.py` — Generation Driver

**Role:** Top-level entry point. Reads config, iterates over header sources, and for each
one invokes the parsing pipeline and converter generation.

**Modes:**

| Mode | Flag | Behaviour |
|---|---|---|
| **pre-extracted** | `--extracted-dir` | Walks pre-aggregated `interfaces/<version>/` folder. Used in CI after `extract-deps` ran. |
| **direct** | (default) | Reads `header_sources` from config directly. Used for local developer builds. |

Types listed in `handcrafted` config section are always skipped.

**New: `--diff-previous` flag** — When supplied with a path to previously generated output,
codegen emits a structural diff (added/removed types, changed field layouts) to stdout
before generating.

#### 6.4.3 Semantic Conflict Detection

During the TypeRegistry merge phase — after all versions of all types have been parsed into
their individual `TypeContainer` instances — the engine performs cross-version field
compatibility analysis before generating any converter code.

**Field-type compatibility check (FR-20):**

For each registered data type, the engine iterates over every field in the generic (superset)
version and traces that field back to every source version where it exists. If the same field
name resolves to different C base types across versions, a diagnostic is emitted:

| Condition | Severity | Example |
|---|---|---|
| Same name, same base type, same dimensions | OK (no diagnostic) | `uint32 timestamp` in V1 and V2 |
| Same name, same base type, different array dimensions | Warning (1) | `uint8 payload[32]` in V1 vs `uint8 payload[64]` in V2 — safe (min-copy), but noted |
| Same name, different base type | Error (2) | `float32 speed` in V1 vs `uint32 speed` in V2 — raw copy produces wrong values |
| Same name, struct vs non-struct | Error (2) | `BatteryInfo_t battery` in V2 vs `uint8 battery` in V1 (hypothetical) |

Severity 2 diagnostics do not halt generation (the converter is still emitted), but they
are prominently displayed and recorded in `field_provenance.json` so maintainers can decide
whether to add a handcrafted adapter, a `field_warnings` annotation, or a corrective
`CallPointer` for custom conversion logic.

**Config-level semantic annotations (`field_warnings`):**

For fields where the base type matches but the *meaning* has changed between versions
(e.g., a `uint8` field that was a bitmask in V1 and became an enum in V3), maintainers can
document this in `config.yaml`:

```yaml
types:
  TelemetryData_t:
    field_warnings:
      status:
        note: "V1-V2: bitmask (bit0=running, bit1=error). V3+: enum (0=idle, 1=running, 2=error, 3=shutdown). Byte-level copy is type-safe but semantically different."
        severity: 1
      position.altitude:
        note: "Renamed to altitude_msl in V3. altitude_agl is a new separate field."
        severity: 0
```

These annotations are:
- Printed during generation alongside the converter for the affected field
- Emitted as comments in the generated C++ converter code
- Recorded in `field_provenance.json` for auditing

**`field_provenance.json` output (FR-21):**

For each field in the generic version, this report lists its provenance across all versions:

```json
{
  "TelemetryData_t": {
    "timestamp": {
      "generic_type": "uint32",
      "versions": {
        "1": { "type": "uint32", "field_name": "timestamp" },
        "2": { "type": "uint32", "field_name": "timestamp" },
        "3": { "type": "uint32", "field_name": "timestamp" }
      },
      "type_compatible": true,
      "warnings": []
    },
    "ground_speed": {
      "generic_type": "float32",
      "versions": {
        "1": { "type": "float32", "field_name": "speed", "rename_from": "speed" },
        "2": { "type": "float32", "field_name": "speed", "rename_from": "speed" },
        "3": { "type": "float32", "field_name": "ground_speed" }
      },
      "type_compatible": true,
      "warnings": []
    },
    "op_status": {
      "generic_type": "uint8",
      "versions": {
        "1": { "type": "uint8", "field_name": "status", "rename_from": "status" },
        "2": { "type": "uint8", "field_name": "status", "rename_from": "status" },
        "3": { "type": "uint8", "field_name": "op_status" }
      },
      "type_compatible": true,
      "warnings": [
        { "severity": 1, "note": "V1-V2: bitmask. V3+: enum. Byte copy is type-safe but semantically different." }
      ]
    },
    "battery": {
      "generic_type": "BatteryInfo_t",
      "versions": {
        "1": null,
        "2": { "type": "BatteryInfo_t", "field_name": "battery" },
        "3": { "type": "BatteryInfo_t", "field_name": "battery" }
      },
      "type_compatible": true,
      "default_applied_for": [1],
      "warnings": []
    }
  }
}
```

This file gives maintainers a single auditable artifact to review the full field-mapping
picture across all versions, identify semantic mismatches, and verify that renames and
defaults are correctly configured.

### 6.5 C Header Parsing Sub-Pipeline

```
Raw .h file on disk
        │
        ▼
 Preprocessor (pluggable)
   Option A: BuiltinPreprocessor (default, no external deps)
     · Strips // and /* */ comments
     · Strips #pragma, #include
     · Captures #define lines
     · Handles simple #ifdef GUARD / #endif include guards
   Option B: ExternalPreprocessor (gcc -E, clang -E, MSVC /EP)
     · Full conditional compilation support
     · Configurable via config.yaml → preprocessor section
        │
        ▼
 Expression Evaluator
   · Evaluates constant integer expressions in #define values
   · Supports: + - * / % parentheses, previously-defined constants
   · Example: #define BUF_SIZE (BASE_SIZE + 4) → resolves to integer
   · Used for array dimensions and version numbers
        │
        ▼
 Tokenizer (Lexer)
   · Token_Symbol, Token_Integer, Token_Float, Token_String
   · Token_Special ({ } ; * [ ] = ( ) , :)
   · Token_Operator (+ - / ^ *)
   · Token_Eof
        │
        ▼
 Parser (Recursive-Descent)
   · typedef struct { ... } Name;             (untagged typedef)
   · typedef struct Tag { ... } Alias;        (tagged typedef)
   · struct Name { ... };                     (C++ style without typedef)
   · typedef enum   { ... } Name;
   · typedef ExistingType NewAlias;
   · typedef Type ArrayAlias[N][M];
   · Nested structs and enums within structs
   · Anonymous struct/union members            (unnamed struct/union inside parent)
   · Forward declarations (struct Foo;)        (recorded, not resolved until used)
   · unsigned, signed, long, const qualifiers
   · Bitfield declarations (: N)
   · Unsupported constructs → warning with     (no silent drops)
     line number, not silent skip
        │
        ▼
 TypeContainer (AST-like model)
   · basictypes   : ~30 pre-registered primitive C types
   · types        : OrderedDict of parsed typedef'd structs/enums
   · defines      : OrderedDict of #define name → evaluated value
   · namespaces   : nested TypeContainers for versioned groupings
```

#### 6.5.1 Expression Evaluator

The expression evaluator handles constant integer expressions that appear in `#define`
macros and array dimension specifications. Without this, headers using computed
constants for array dimensions or version numbers would fail to parse.

**Supported operations:** `+`, `-`, `*`, `/`, `%`, parentheses, unary minus, bitwise
`&`, `|`, `^`, `~`, `<<`, `>>`.

**Constant substitution:** The evaluator maintains a symbol table built from previously
parsed `#define` values. When it encounters an identifier in an expression, it looks up
that identifier and substitutes its integer value.

**Scope:** Only integer expressions. Float expressions and string concatenation are not
evaluated (not needed for struct layout determination).

```python
# Example: given these #defines in order:
#   #define BASE_SIZE 32
#   #define BUF_SIZE (BASE_SIZE + 4)
#   #define ARRAY_DIM (BUF_SIZE / 2)

evaluator.evaluate("BASE_SIZE")           # → 32
evaluator.evaluate("(BASE_SIZE + 4)")     # → 36
evaluator.evaluate("(BUF_SIZE / 2)")      # → 18
evaluator.evaluate("unparseable_expr")    # → None (caller handles gracefully)
```

### 6.6 Pointer Abstraction Layer

The converter engine simultaneously walks a **source** struct tree and a **destination**
struct tree, handling structural mismatches through a uniform pointer interface.

#### Uniform Interface

Every pointer type exposes the same duck-type protocol:

| Property / Method | Description |
|---|---|
| `is_struct` | True if this node is a struct (non-leaf) |
| `is_array` | True if this node is a C array |
| `is_basic_type` | True if this node is a scalar leaf |
| `pass_able` | True if this pointer becomes a function parameter in generated code |
| `enter_struct(field_name, type_hint)` | Navigate into a named sub-field; returns child pointer or `None` |
| `enter_array(dest)` | Navigate into array element; returns element-level pointer |
| `array_dimensions` | List of dimension sizes (one per axis) |
| `parent_source` | The parent pointer (for parameter scope) |

#### Pointer Types

**`StructPointer`** — Wraps a `CType` from `TypeContainer` plus a versioned C++ namespace.

Member lookup uses a **three-step strategy with ambiguity detection**:
1. Exact name match
2. `name + "_" + type_hint` match
3. Strip type suffix and retry

**NEW guard:** If steps 2 or 3 produce multiple candidates, an `AmbiguousMemberError` is
raised instead of picking the first match silently.

**`NamedSourcePointer`** — Passive proxy that activates on `enter_struct(registered_name)`.
Used for transparent field renames.

**`ValuePointer`** — Wraps a tree of explicit default/override values. Never becomes a
function parameter.

**`WarningNullPointer`** — Null-safe catch-all fallback at index 0 in every `SourceContainer`.
Emits configurable diagnostics.

**`CallPointer`** — Dispatches to a user-supplied callable for fields requiring custom
computation.

#### `SourceContainer`

Manages an **ordered, priority-ranked list** of pointers for one destination struct node:
- Tracks which sources are used, child-used, and top-level
- Drives generated function signatures (only `pass_able` + `used` pointers become parameters)
- `update_source_constructors(dest)` resolves the best source per field and records usage

### 6.7 Project-Variant Configuration Layer

This layer is the **only** part that changes between projects.

#### 6.7.1 Configuration File Format

A single YAML file provides all project configuration:

```yaml
# config.yaml — validated at load time against a JSON schema

project:
  name: reference_project
  description: "Reference project for adapter generation"
  generic_version_sentinel: 9999

# Preprocessor selection (default: builtin)
preprocessor:
  type: builtin          # or "external"
  # command: "gcc -E"    # only when type: external
  # flags: ["-D__TARGET_ARCH__"]

# Where to find versioned headers
header_sources:
  - path: "headers/v1"
    version_tag: "v1"
  - path: "headers/v2"
    version_tag: "v2"
  - path: "headers/v3"
    version_tag: "v3"

additional_includes:
  - "headers"   # for platform_types.h

# Type registration
types:
  TelemetryData_t:
    version_macro: TELEMETRY_DATA_VERSION
    generate_reverse: true       # Generate Generic→V converters
    defaults:
      battery.voltage: "0.0"
      signal_quality: "0"
      # ... more defaults ...
    renames:
      speed: ground_speed        # old_name: new_name
      status: op_status
    field_warnings:               # Document known semantic changes
      op_status:
        note: "V1-V2 uses bitmask; V3+ uses enum. Byte copy is safe but meaning differs."
        severity: 1
      position.altitude_msl:
        note: "Was 'altitude' in V1-V2, renamed to 'altitude_msl' in V3. altitude_agl is new."
        severity: 0

  CommandMessage_t:
    version_macro: COMMAND_MSG_VERSION
    defaults:
      source_id: "0"
      checksum: "0"

handcrafted: []                  # Types with manual adapters

warnings:
  min_display_severity: 1
  color: true
```

**Validation:** The config loader validates against a JSON schema at load time. Missing
required fields, unknown keys, and type mismatches produce actionable error messages with
file path and line number.

#### 6.7.2 Default-Value Modules

```
variants/<project>/defaults/
├── __init__.py
├── gen_base.py         Abstract base (Template Method pattern)
└── gen_<module>.py     Per-module default values and renames
```

**`GenerateDataTypeBase`** enforces a fixed three-step init sequence:

```python
class GenerateDataTypeBase:
    def __init__(self, type_registry, config):
        self._registry = type_registry
        self._config = config
        self._insert_defines()                    # step 1: override #defines
        self._create_data_types()                 # step 2: register types
        self._add_defaults_and_conversions()      # step 3: attach defaults/renames
```

### 6.8 Generated Output Artifacts

#### `data_types/<TypeName>.h` — Versioned Namespace Header

```cpp
#pragma once
#include "platform_types.h"

// Compile-time guard: ensure sentinel never collides with real versions
static_assert(TELEMETRY_DATA_VERSION != 9999,
    "Version 9999 is reserved as the generic adapter hub version");

namespace TelemetryData_t_V_1 {
  static const uint32_t VERSION = 1;
  typedef struct { /* fields as in V1 */ } TelemetryData_t;
}

namespace TelemetryData_t_V_2 {
  static const uint32_t VERSION = 2;
  typedef struct { /* fields as in V2 */ } TelemetryData_t;
}

namespace TelemetryData_t_V_Gen {
  static const uint32_t VERSION = 9999;
  typedef struct { /* superset of all fields */ } TelemetryData_t;
}
```

#### `converters/generated/Converter_<TypeName>.h` — Converter Class

```cpp
#include "adapter_base.h"
#include "version_info.h"
#include "data_types/TelemetryData_t.h"

class Converter_TelemetryData_t : public AdapterConverterBase
{
public:
    static const char* GetConverterTypeName();  // std::string, not wchar_t*
    static AdapterConverterBase* Create();

    const char* GetTypeName() const override;

    long ConvertData(
        uint32_t src_type_tag,  unsigned long src_size,
        const IVersionInfo& src_version,
        uint32_t dst_type_tag,  unsigned long dst_size,
        const IVersionInfo* dst_version,
        void* dst_data,
        void** out_data, unsigned long& out_size) override;

    long GetDefaultValue(
        uint32_t type_tag, unsigned long size,
        const IVersionInfo& version,
        void** default_data, unsigned long& default_size) override;

    bool AreVersionsCompatible(
        uint32_t src_type_tag, unsigned long src_size,
        const IVersionInfo& src_version,
        uint32_t dst_type_tag, unsigned long dst_size,
        const IVersionInfo& dst_version) override;

private:
    // Forward converters: V_N → Generic
    void convert_V1_to_Generic(
        TelemetryData_t_V_Gen::TelemetryData_t& dest,
        const TelemetryData_t_V_1::TelemetryData_t& source);

    void convert_V2_to_Generic(
        TelemetryData_t_V_Gen::TelemetryData_t& dest,
        const TelemetryData_t_V_2::TelemetryData_t& source);

    // Reverse converters (when generate_reverse: true)
    void convert_Generic_to_V1(
        TelemetryData_t_V_1::TelemetryData_t& dest,
        const TelemetryData_t_V_Gen::TelemetryData_t& source);

    void convert_Generic_to_V2(
        TelemetryData_t_V_2::TelemetryData_t& dest,
        const TelemetryData_t_V_Gen::TelemetryData_t& source);
};
```

#### `converters/generated/converters.cpp` — Factory Registration

```cpp
#include <vector>
#include <string>
#include <functional>
#include "Converter_TelemetryData_t.h"
#include "Converter_CommandMessage_t.h"
#include "Converter_SystemStatus_t.h"

struct ConverterRegistration {
    std::string type_name;
    std::function<AdapterConverterBase*()> factory;
};

std::vector<ConverterRegistration> GetGeneratedAdapters()
{
    return {
        { Converter_TelemetryData_t::GetConverterTypeName(),
          Converter_TelemetryData_t::Create },
        { Converter_CommandMessage_t::GetConverterTypeName(),
          Converter_CommandMessage_t::Create },
        { Converter_SystemStatus_t::GetConverterTypeName(),
          Converter_SystemStatus_t::Create },
    };
}
```

---

## 7. End-to-End Data Flow

```
  ┌──────────────────────────────────────────────────────────────────┐
  │  INPUTS                                                           │
  │  · config.yaml (types, defaults, renames, schema paths, format)   │
  │  · Schema files: C headers, .proto, .json schema, or mixed        │
  └──────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼  [CLI: ductape generate]
              ┌───────────────────────────────────────────┐
              │  1. Load + validate config.yaml            │
              │  2. Select parser frontend per source:     │
              │     · format: c_header → C Header Parser   │
              │     · format: protobuf → Protobuf Parser   │
              │     · format: json_schema → JSON Parser    │
              │  3. Each frontend produces TypeContainer    │
              │  4. Merge into TypeRegistry with            │
              │     cross-source conflict detection         │
              └──────────────────┬────────────────────────┘
                                  │
                       TypeContainer IR (format-agnostic)
                                  │
                          ┌───────▼────────┐
                          │  TypeRegistry  │
                          └───────┬────────┘
                                  │  for each registered type
                                  ▼
                  ┌───────────────────────┐    ┌──────────────────────────┐
                  │  DataType             │◄───│  config.yaml defaults    │
                  │    DataTypeVersion[0] │    │  config.yaml renames     │
                  │    DataTypeVersion[1] │    │  defaults/gen_*.py       │
                  │    DataTypeVersion[N] │    └──────────────────────────┘
                  └───────────┬───────────┘
                              │
                      for each version pair
                              │
                              ▼
                  ┌───────────────────────┐
                  │  Converter            │
                  │  SourceContainer walk │
                  │  · Forward: V→Gen     │
                  │  · Reverse: Gen→V     │
                  │    (if configured)    │
                  └───────────┬───────────┘
                              │
                              ▼  [Selected Code Emitter]
              ┌────────────────────────────────────────────────────┐
              │  OUTPUT (varies by emitter)                         │
              │  · cpp:        Converter_*.h/cpp, converters.cpp   │
              │  · python:     converter_*.py modules               │
              │  · rust:       converter_*.rs with From<> impls     │
              │  · shared_lib: adapter_*.so with C ABI              │
              │                                                     │
              │  Always: version_overview.json                      │
              │  Always: field_provenance.json                      │
              └────────────────────────────────────────────────────┘

  TWO-STAGE VARIANT (when format: multi_source):

  Source A (protobuf)    Source B (c_header)    Source C (json)
       │                      │                      │
       ▼                      ▼                      ▼
  ┌─────────┐           ┌─────────┐           ┌─────────┐
  │ Stage 1 │           │ Stage 1 │           │ Stage 1 │
  │ V1→V3   │           │ V1→V2   │           │ V1→V2   │
  │ (intra) │           │ (intra) │           │ (intra) │
  └────┬────┘           └────┬────┘           └────┬────┘
       │ proto canonical     │ C canonical         │ JSON canonical
       └─────────┬───────────┴─────────┬───────────┘
                 ▼                     ▼
           ┌────────────────────────────────┐
           │  Stage 2: Cross-format          │
           │  All canonicals → platform hub  │
           └───────────────┬────────────────┘
                           ▼
                  Platform canonical model
```

---

## 8. Key Data Models

### `TypeContainer`

```
TypeContainer
├── basictypes   : OrderedDict[str → CType]
│   └── ~30 pre-seeded primitive C types
├── types        : OrderedDict[str → CType]
│   └── CType { name, is_struct, is_enum, is_basic_type, is_array,
│                dimensions[], members[], enum_values[], aliased_type }
├── defines      : OrderedDict[str → str | int]
│                  (values evaluated by ExpressionEvaluator where possible)
├── namespaces   : OrderedDict[str → TypeContainer]
└── (no function_declarations — removed, not needed for struct adapters)
```

### `DataType`

```
DataType
├── name               : str         e.g. "TelemetryData_t"
├── class_name         : str         e.g. "Converter_TelemetryData_t"
├── version_macro      : str         e.g. "TELEMETRY_DATA_VERSION"
├── generate_reverse   : bool        whether to emit Generic→V converters
├── versions           : list[DataTypeVersion]
├── converters         : OrderedDict[key → Converter]
└── container          : TypeContainer
```

### `DataTypeVersion`

```
DataTypeVersion
├── name               : str
├── version            : NumberedVersion(int) | GenericVersion  tagged type
├── namespace          : str         e.g. "TelemetryData_t_V_2"
├── c_type             : CType       struct layout
├── sources            : list[(Pointer, priority)]
└── struct_pointer     : StructPointer
```

### `Converter`

```
Converter
├── destination      : DataTypeVersion
├── source           : DataTypeVersion | None
├── direction        : "forward" | "reverse"    
├── sources          : SourceContainer
├── skip_generation  : bool
└── root_element     : ConverterElement
    └── child_converters : list[...]
```

---

## 9. Interfaces & Integration Points

### 9.1 Input Interfaces

| Interface | Format | Consumed By |
|---|---|---|
| Versioned C headers | `typedef struct` + `#define VERSION N` | Parser via InterfaceVersion |
| `config.yaml` | YAML with JSON schema validation | cli.py, codegen.py |
| C/C++ package dirs | Folder layout: `include/`, `stubs/` | dependency\_extractor |

### 9.2 Output Interfaces

| Artifact | Consumer |
|---|---|
| `data_types/<Type>.h` | Project build system (C++ emitter) |
| `Converter_<Type>.h/cpp` | Project build system (C++ emitter) |
| `converters.cpp` | Adapter runtime via `GetGeneratedAdapters()` (C++ emitter) |
| `converter_<type>.py` | Plugin systems, test harnesses (Python emitter) |
| `converter_<type>.rs` | Safety-critical builds (Rust emitter) |
| `adapter_<type>.so` / `.dll` | Runtime hot-reload via `dlopen` (shared library emitter) |
| `version_overview.json` | Developers and CI for auditing |
| `version_diff.json` | Developers for PR/release review |
| `field_provenance.json` | Developers for semantic consistency auditing — shows per-field type provenance, renames, defaults, and configured warnings across all versions |

### 9.3 Runtime Interface (Generated Code Contract)

Generated converters inherit from `AdapterConverterBase`. **Key design choices:**
- `const char*` for type names (portable across OS — avoids `wchar_t` size differences)
- `uint32_t type_tag` for type dispatch (no vendor-specific framework types)

```cpp
class AdapterConverterBase {
public:
    virtual ~AdapterConverterBase() = default;

    virtual const char* GetTypeName() const = 0;

    virtual long ConvertData(
        uint32_t src_type_tag, unsigned long src_size,
        const IVersionInfo& src_version,
        uint32_t dst_type_tag, unsigned long dst_size,
        const IVersionInfo* dst_version,
        void* dst_data,
        void** out_data, unsigned long& out_size) = 0;

    virtual long GetDefaultValue(
        uint32_t type_tag, unsigned long size,
        const IVersionInfo& version,
        void** default_data, unsigned long& default_size) = 0;

    virtual bool AreVersionsCompatible(
        uint32_t src_type_tag, unsigned long src_size,
        const IVersionInfo& src_version,
        uint32_t dst_type_tag, unsigned long dst_size,
        const IVersionInfo& dst_version) = 0;
};

class IVersionInfo {
public:
    virtual ~IVersionInfo() = default;
    virtual uint32_t GetVersion() const = 0;
    virtual const char* GetComponentName() const = 0;
};
```

---

## 10. Design Patterns & Rationale

### Template Method — Type Generator Configuration

`GenerateDataTypeBase.__init__()` calls `_insert_defines`, `_create_data_types`,
`_add_defaults_and_conversions` in fixed order. Subclasses override only what they need.

**Rationale:** Prevents accidental step omission. Sequence enforced by code, not convention.

### Uniform Pointer Interface — Duck-Type Navigation

All pointer types share `enter_struct()`/`enter_array()`/`is_struct` protocol. The converter
engine never performs `isinstance()` checks.

**Rationale:** Single-pass tree walking handles structs, defaults, renames, and null-safety.
New pointer behaviours only require implementing the protocol.

### Priority-Based Source Selection

`SourceContainer` holds sources with integer priorities. Highest-priority applicable source
wins per field. Standard levels: `DEFAULT_PRIORITY=50`, `OVERRIDE_PRIORITY=200`.

**Rationale:** Layered behaviours without engine-level conditionals.

### Hub-and-Spoke Versioning — Linear Converter Count

All converters route through the generic hub. Forward: N converters. Reverse (optional):
additional N converters. Total: at most 2N, never N².

### Tagged Version Type

Python model uses `GenericVersion` vs `NumberedVersion(N)` — distinct types that the
type checker enforces. C++ output uses a sentinel integer guarded by `static_assert`.

**Rationale:** Eliminates the risk of magic-number collisions at both the Python level
(type error) and C++ level (compile-time assertion).

### Per-Package Parsing with Conflict Detection

Each package is parsed into its own `TypeContainer`. The `TypeRegistry` merge step detects
name collisions across packages and raises actionable errors.

**Rationale:** Eliminates the header-concatenation bug where identically-named types from
different packages silently conflict.

---

## 11. Error Handling & Diagnostics

### Warning Module

Centralised `WarningModule` with configurable severity, coloured output (with `--no-color`),
and two categories: **missing sources** (batched, printed at end) and **version conflicts**
(fatal, raised immediately).

| Severity | Meaning | Colour |
|---|---|---|
| 0 (info) | Trace / non-actionable | Default |
| 1 (warning) | Field not found; default applied | Yellow |
| 2 (error) | Field not found; no default; zero-initialised | Red |

### Version Conflict Detection

Same version number + structurally different layouts → `VersionConflictError` with
type name, version number, and both layouts summarised.

### Ambiguous Member Detection

Fuzzy member lookup returning multiple candidates → `AmbiguousMemberError` listing all
candidates so the developer can add an explicit rename directive.

### Semantic Conflict Detection

During TypeRegistry merge, cross-version field-type compatibility is checked for every field
in the generic hub version. Diagnostics are graded by severity:

| Condition | Severity | Action |
|---|---|---|
| Same name, same base type, same dimensions | 0 (info) | No diagnostic |
| Same name, same base type, different array dimensions | 1 (warning) | Logged; min-copy is safe but noted |
| Same name, different base type | 2 (error) | Prominently displayed; recorded in `field_provenance.json` |
| Same name, struct vs non-struct | 2 (error) | Prominently displayed; consider handcrafted adapter |
| `field_warnings` annotation present in config | Configured | Printed during generation; emitted as C++ comment in converter |

Severity 2 diagnostics do **not** halt generation — the converter is still emitted, and the
raw byte-level copy still compiles. The diagnostic ensures maintainers are aware of the
mismatch and can decide to add a `CallPointer` for custom conversion logic, a handcrafted
adapter, or a `field_warnings` annotation documenting the known semantic difference.

All diagnostics are also recorded in `field_provenance.json` alongside the per-field
provenance data, giving maintainers a single auditable artifact for the entire type's
cross-version field mapping.

### Unsupported Parser Construct Warning

When the parser encounters a C construct it cannot handle (e.g., function-like macros,
complex preprocessor conditionals not flattened by the external preprocessor, inline
assembly), it emits a warning with the file name and line number and continues parsing.
This ensures unrecognised constructs are never silently skipped.

### Config Validation Errors

Invalid YAML config → actionable error with field path, expected type, and suggestion.

---

## 12. Testing Strategy

### 12.1 Golden-File Regression Testing

The reference project includes `expected_output/` with checked-in generated files. CI runs:

```bash
ductape verify \
    --config variants/reference_project/config.yaml \
    --expected variants/reference_project/expected_output/
```

This compares generated output file-by-file against the expected output. Any structural
difference fails the build with a clear diff.

### 12.2 Unit Tests

| Module | Test Focus |
|---|---|
| Preprocessor | Comment stripping, #define capture, multiline defines |
| Expression Evaluator | Arithmetic, constant substitution, hex literals, error cases |
| Tokenizer | Token classification, edge cases (hex, suffixed ints, strings) |
| Parser | Struct/enum/alias parsing, nested structs, arrays, qualifiers, C++ style `struct Name {}`, tagged typedefs, anonymous struct/union members, forward declarations, unsupported-construct warnings |
| Config | Schema validation, missing fields, type coercion, error messages, field\_warnings parsing |
| Converter Generation | Field mapping, defaults, renames, array dimension handling, skip identical versions |
| Semantic Conflict Detection | Field-type compatibility across versions, field\_warnings propagation, field\_provenance.json correctness |
| Ambiguity Detection | Fuzzy lookup with multiple candidates raises AmbiguousMemberError |

### 12.3 Round-Trip Verification (for reverse converters)

When `generate_reverse: true`, a test harness populates a V_N struct, converts
V_N → Generic → V_N, and verifies the round-trip preserves all shared fields.

---

## 13. Extension Guide

### Adding a New Data Type

1. Add entry to `config.yaml` under `types:`
2. Add default values under the type's `defaults:` section
3. Optionally add renames under `renames:`
4. Run `ductape generate`

### Adding a New Project Variant

1. Create `variants/<my_project>/config.yaml`
2. Create `variants/<my_project>/defaults/` with gen_base.py and gen_<module>.py
3. Add versioned headers (or configure package manager paths)
4. Run `ductape generate --config variants/<my_project>/config.yaml`

### Declaring a Field Rename

In `config.yaml`:

```yaml
types:
  MyType_t:
    renames:
      old_field_name: new_field_name
```

### Adding a Handcrafted Adapter

1. Add the type name to `handcrafted:` list in config.yaml
2. Implement manually following `AdapterConverterBase` interface
3. Register in downstream build system alongside `converters.cpp`

---

## 14. Multi-Format Extension Architecture

### 14.1 Motivation

The core adapter generation engine — `TypeContainer`, hub-and-spoke conversion, pointer
abstractions, priority-based source selection, field provenance — operates on a **format-
agnostic intermediate representation**: data types with named fields, each having a base
type, optional array dimensions, and version metadata. This IR is the same whether the
original schema was a C header, a Protobuf definition, a JSON Schema, or any other
structured data description language.

This section specifies how the architecture extends to support multiple schema formats and
multiple output languages through pluggable frontends and backends, without modifying the
core engine.

### 14.2 Architecture: Frontend → IR → Engine → Backend

```
 PARSER FRONTENDS (pluggable)         SHARED CORE (unchanged)         CODE EMITTERS (pluggable)
 ─────────────────────────            ──────────────────────          ─────────────────────────
 C Header Parser ─────┐                                              ┌───── C++ Class Emitter
 Protobuf Parser ─────┼──► TypeContainer ──► Hub-and-Spoke ──► ─────┼───── Python Emitter
 JSON Schema Parser ──┤     (shared IR)       Engine                 ├───── Rust Emitter
 [Future: IDL, Avro,  │                                              ├───── Shared Library (.so)
  FlatBuffers, ...]  ─┘                                              └───── [Future: Go, TS, ...]
```

**Key invariant:** Adding a new parser frontend or code emitter never requires modifying
the core engine, any existing frontend, or any existing emitter. Each plugin is a self-
contained module that conforms to a defined interface.

### 14.3 Parser Frontend Interface

Every parser frontend implements the same contract:

```python
class ParserFrontend:
    """Interface that all parser frontends implement."""

    # Identifier used in config.yaml: format: "c_header" | "protobuf" | "json_schema" | ...
    format_id: str

    def parse(self, schema_path: str, config: dict) -> TypeContainer:
        """
        Parse a schema file and return a populated TypeContainer.

        The TypeContainer must contain:
        - types: OrderedDict of parsed data types (structs/messages/objects)
        - defines: OrderedDict of version constants (if applicable)
        - Each type's members with: name, base_type, is_array, dimensions

        Args:
            schema_path: Path to the schema file
            config: The type's configuration from config.yaml

        Returns:
            Populated TypeContainer
        """
        raise NotImplementedError
```

#### Supported Frontends

**C Header Parser** (existing)
- Input: `.h` files with `typedef struct`, `#define VERSION N`
- Handles: structs, enums, aliases, nested types, arrays, bitfields
- Expression evaluator resolves computed constants

**Protobuf Parser** (new)
- Input: `.proto` files (proto2 and proto3 syntax)
- Maps `message` → struct, `enum` → enum, `repeated` → array, `map` → key-value struct
- Tracks field numbers for backward-compatibility analysis
- `oneof` fields mapped as a union with a discriminator tag
- Nested messages mapped as nested structs

**JSON Schema Parser** (new)
- Input: `.json` schema files (JSON Schema draft-07 and later)
- Maps `object` → struct, `array` → array, `$ref` → type reference
- `additionalProperties` and `patternProperties` mapped as opaque blobs with a warning
- `enum` constraints mapped to enum types

**Future frontends** (planned, not in initial release):
- DDS IDL (`.idl`): structs, sequences, bounded strings, unions
- Apache Avro (`.avsc`): records, arrays, maps, unions
- FlatBuffers (`.fbs`): tables, structs, vectors, unions

### 14.4 Code Emitter Interface

Every code emitter implements:

```python
class CodeEmitter:
    """Interface that all code emitters implement."""

    # Identifier used in config.yaml: emitter: "cpp" | "python" | "rust" | "shared_lib"
    emitter_id: str

    def emit_type_header(self, data_type: DataType, output_dir: str):
        """Emit versioned type definitions."""
        raise NotImplementedError

    def emit_converter(self, converter: Converter, output_dir: str):
        """Emit a single converter (forward or reverse)."""
        raise NotImplementedError

    def emit_factory(self, all_types: list[DataType], output_dir: str):
        """Emit the factory/registry that lists all generated converters."""
        raise NotImplementedError
```

#### Supported Emitters

**C++ Class Emitter** (existing)
- Output: `Converter_<Type>.h/cpp` + `converters.cpp` factory
- Namespace-isolated versions, `AdapterConverterBase` inheritance
- `static_assert` sentinel guard

**Python Function Emitter** (new)
- Output: `converter_<type>.py` modules with pure-Python converter functions
- Suitable for: plugin systems, test harnesses, data pipeline tools
- No compiled dependencies; uses `dataclasses` for type definitions

**Rust Trait Emitter** (new)
- Output: `converter_<type>.rs` with `impl From<V1> for Generic` trait implementations
- Compile-time type safety; memory-safe field copying
- Suitable for: safety-critical systems, high-performance data buses

**Shared Library Emitter** (new)
- Output: `.so`/`.dll` with stable C ABI
- Exports: `GetConverterVersion()`, `ConvertData()`, `GetSupportedVersions()`
- Loadable at runtime via `dlopen`/`LoadLibrary` without process restart
- Suitable for: middleware platforms that need to add adapters for new data sources
  without downtime

### 14.5 Two-Stage Adaptation

For platforms that ingest data from multiple sources using different serialization formats,
the tool supports a **two-stage adaptation pipeline** configured in a single YAML file:

```yaml
# Two-stage config: ingestion from a Protobuf source into a platform canonical model

sources:
  telemetry_feed:
    format: protobuf
    schema_versions:
      - path: "schemas/telemetry_v1.proto"
        version_tag: "v1"
      - path: "schemas/telemetry_v2.proto"
        version_tag: "v2"
      - path: "schemas/telemetry_v3.proto"
        version_tag: "v3"

    # Stage 1: Intra-format versioning (Protobuf V1/V2/V3 → Protobuf canonical)
    stage1:
      hub_version: "v3"           # Latest Protobuf version is the intra-format hub
      types:
        SensorReading:
          version_field: "schema_version"
          defaults:
            confidence: "0.0"
            source_quality: "1"
          renames:
            speed: ground_speed

    # Stage 2: Cross-format normalization (Protobuf canonical → platform canonical)
    stage2:
      target_format: c_header
      target_schema: "platform/canonical_types.h"
      type_mappings:
        SensorReading: PlatformTrack_t    # Protobuf SensorReading → C struct PlatformTrack_t
      field_mappings:
        SensorReading:
          latitude: position.lat
          longitude: position.lon
          ground_speed: kinematics.speed
          altitude_m: position.alt_msl
```

Both stages use the same hub-and-spoke engine. Stage 1 operates within a single format
family (all Protobuf, or all C structs, or all JSON schemas). Stage 2 operates across
format families. The field mapping, default injection, rename handling, and provenance
tracking are identical in both stages.

### 14.6 Config Extensions for Multi-Format

The `config.yaml` schema is extended with optional fields:

```yaml
project:
  name: data_platform_adapters
  description: "Adapters for heterogeneous data source ingestion"
  generic_version_sentinel: 9999

# Schema format (default: c_header for backward compatibility)
format: c_header           # or: protobuf, json_schema, multi_source

# Code emitter (default: cpp for backward compatibility)
emitter: cpp               # or: python, rust, shared_lib

# For multi_source format: list of heterogeneous sources
sources:                   # Only used when format: multi_source
  - name: legacy_sensor
    format: c_header
    # ... stage1/stage2 config ...
  - name: modern_service
    format: protobuf
    # ... stage1/stage2 config ...
  - name: external_api
    format: json_schema
    # ... stage1/stage2 config ...
```

When `format` is a single value (not `multi_source`), the tool behaves exactly as the
original C-struct-only architecture — full backward compatibility.

### 14.7 Repository Structure Additions

```
ductape/
│   ├── frontends/                    ◄── PARSER FRONTENDS (pluggable)
│   │   ├── __init__.py
│   │   ├── frontend_base.py          Abstract ParserFrontend interface
│   │   ├── c_header.py               C header parser (wraps existing conv/ pipeline)
│   │   ├── protobuf.py               Protobuf .proto parser → TypeContainer
│   │   └── json_schema.py            JSON Schema parser → TypeContainer
│   │
│   ├── emitters/                     ◄── CODE EMITTERS (pluggable)
│   │   ├── __init__.py
│   │   ├── emitter_base.py           Abstract CodeEmitter interface
│   │   ├── cpp_emitter.py            C++ class emitter (wraps existing CodeWriter)
│   │   ├── python_emitter.py         Python converter function emitter
│   │   ├── rust_emitter.py           Rust trait implementation emitter
│   │   └── shared_lib_emitter.py     Shared library (.so/.dll) emitter
│   │
│   └── conv/                         ◄── CORE ENGINE (unchanged)
│       └── ...                       (all existing modules, no modifications)
```

### 14.8 Design Principle: Core Isolation

The multi-format extension is designed so that:

1. **The core engine (`conv/`) is never modified.** All new code lives in `frontends/`
   and `emitters/`. The `TypeContainer` IR is the stable contract between them.

2. **Existing C-struct-only projects work unchanged.** The default `format: c_header`
   and `emitter: cpp` settings preserve full backward compatibility. No existing config
   files need updating.

3. **New formats are additive.** Adding support for a new schema format (e.g., Avro)
   requires only a new file in `frontends/` that implements `ParserFrontend`. No other
   module is touched.

4. **New output languages are additive.** Adding a new emitter (e.g., Go) requires only
   a new file in `emitters/` that implements `CodeEmitter`. No other module is touched.

5. **Two-stage adaptation composes naturally.** Stage 1 and Stage 2 are both invocations
   of the same hub-and-spoke engine with different input TypeContainers. No special-case
   logic exists for multi-stage pipelines.

---

## 15. Glossary

| Term | Definition |
|---|---|
| **Generic version** | Superset struct acting as the hub. Contains the union of all fields across all versions. Represented by `GenericVersion` tag in Python, sentinel integer in C++. |
| **Hub-and-spoke** | Pattern where all converters route through the generic hub (2N converters max, not N²). |
| **Forward converter** | V_N → Generic conversion. Always generated. |
| **Reverse converter** | Generic → V_N conversion. Generated when `generate_reverse: true`. |
| **Interface package** | A C/C++ package providing versioned header files for one software module. |
| **AdapterConverterBase** | Abstract C++ base class. All generated converters inherit from it. |
| **IVersionInfo** | Interface delivering version numbers at runtime. |
| **TypeContainer** | In-memory AST-like model built by the C parser. |
| **InterfaceVersion** | One interface package at one version. Owns a TypeContainer. |
| **DataType** | One logical C struct type across all versions. Owns all DataTypeVersions and Converters. |
| **DataTypeVersion** | One (type, version) pair with struct layout and default-value sources. |
| **SourceContainer** | Priority-ranked pointer list for resolving field sources during tree walking. |
| **ValuePointer** | Tree of constant values navigable with the pointer protocol. |
| **RenameOp** | Directive mapping old field name → new field name via NamedSourcePointer. |
| **Expression Evaluator** | Resolves constant integer expressions in #define macros. |
| **Golden-file test** | Regression test comparing generated output against checked-in reference. |
| **Field provenance report** | `field_provenance.json` — per-field audit artifact listing which versions contribute each field in the generic hub, their C types, rename history, configured warnings, and type-compatibility status. |
| **Field-type compatibility check** | Cross-version analysis during TypeRegistry merge that detects when the same field name has different C base types across versions and emits graded diagnostics. |
| **`field_warnings`** | Optional config.yaml section documenting known semantic changes to fields whose C type is compatible but whose meaning has changed between versions (e.g., bitmask → enum). Propagated as C++ comments and recorded in field\_provenance.json. |
| **AmbiguousMemberError** | Error raised when fuzzy member lookup matches multiple candidates for a field name, requiring the developer to add an explicit rename directive. |
| **Forward declaration** | `struct Foo;` — recorded by the parser for type resolution but not fully parsed until the complete definition is encountered. |
| **Parser frontend** | (NEW — Multi-Format) A pluggable module that reads a specific schema format (C headers, Protobuf, JSON Schema, etc.) and populates the shared TypeContainer intermediate representation. New formats are added by implementing the `ParserFrontend` interface. |
| **Code emitter** | (NEW — Multi-Format) A pluggable module that consumes the converter model and emits converter code in a specific language (C++, Python, Rust, shared library). New languages are added by implementing the `CodeEmitter` interface. |
| **TypeContainer IR** | The shared intermediate representation that all parser frontends produce and the core engine consumes. Format-agnostic: contains types, fields, base types, array dimensions, and version metadata regardless of the original schema format. |
| **Two-stage adaptation** | (NEW — Multi-Format) A pipeline where Stage 1 normalizes within a single format family (e.g., Protobuf V2→V5) and Stage 2 normalizes across format families (e.g., Protobuf canonical → platform canonical C struct). Both stages use the same hub-and-spoke engine. |
| **Intra-format adaptation** | (NEW — Multi-Format) Stage 1 of two-stage adaptation: converting between versions of the same schema format. Example: Protobuf schema V1 → Protobuf schema V3. |
| **Cross-format normalization** | (NEW — Multi-Format) Stage 2 of two-stage adaptation: converting from one schema format's canonical form into a different format's canonical form. Example: Protobuf canonical → C struct canonical. |
| **Hot-reloadable adapter** | (NEW — Multi-Format) A converter compiled as a shared library (`.so`/`.dll`) with a stable C ABI, loadable at runtime via `dlopen` without process restart. Enables adding support for new data source versions without downtime. |
