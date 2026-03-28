# ductape

**The missing tool for C struct version management.**

ductape parses versioned C struct headers and generates compilable converter
code using a hub-and-spoke pattern. Config-driven: YAML in, C++ out. Zero
manual converter code.

## The problem

When firmware evolves, struct layouts change. Fields get added, renamed, resized.
With 3 data types across 3 firmware versions, you need **18 manual converter
functions** (6 forward + 6 reverse + boilerplate). With 10 types across 5 versions,
that's **100+**. Every one is hand-written, tested, and maintained. Every one is a
bug waiting to happen.

## The solution

ductape uses a **hub-and-spoke** pattern. Instead of converting between every
version pair (N²), it designates one **generic hub version** — the superset of
all fields — and generates only 2N converters:

```
V1 ──► Generic (hub)  ──► V1
V2 ──► Generic (hub)  ──► V2
V3 ──► Generic (hub)  ──► V3
```

You write a YAML config. ductape generates the C++. The generated code compiles.
The field provenance is auditable. That's it.

## Who this is for

- **Embedded firmware teams** — devices in the field running different firmware versions
- **Automotive ECU developers** — CAN messages evolving across model years
- **Aerospace/defence** — telemetry structs across avionics software revisions
- **IoT platforms** — aggregating data from heterogeneous device populations
- **Anyone with versioned C structs** — if you maintain manual converters today, ductape replaces them

## Who this is NOT for

Teams already using **protobuf**, **Avro**, or **FlatBuffers** — those formats
handle version tolerance natively via their wire format. ductape fills the gap
for teams whose data lives in **raw C structs**.

## Quick start

```bash
pip install -e .

# Generate adapters from versioned headers
ductape generate \
    --config variants/reference_project/config.yaml \
    --output build/

# Compile the generated C++
g++ -c build/converters/generated/*.cpp \
    -Ibuild -Iruntime_reference \
    -Ibuild/converters/generated -std=c++17

# Verify against golden files
ductape verify \
    --config variants/reference_project/config.yaml \
    --expected variants/reference_project/expected_output/
```

## Proof: real generated output

The reference project models a **drone telemetry system** evolving across 3
firmware versions. Here's what happens:

### Input: V1 header (7 fields, firmware 1.0)

```c
#define TELEMETRY_DATA_VERSION 1
#define MAX_PAYLOAD_SIZE 32

typedef struct {
    uint32 timestamp;
    float32 speed;           // ← renamed to ground_speed in V3
    float32 altitude;        // ← renamed to altitude_msl in V3
    float32 heading;
    float32 latitude;
    float32 longitude;
    uint8 status;            // ← renamed to op_status in V3
    uint8 payload[MAX_PAYLOAD_SIZE];
} TelemetryData_t;
```

### Input: V3 header (15 fields, firmware 3.0)

```c
#define TELEMETRY_DATA_VERSION 3
#define MAX_PAYLOAD_SIZE 64

typedef struct {
    float32 voltage;
    float32 current;
    uint8 charge_percent;
} BatteryInfo_t;

typedef struct {
    uint32 timestamp;
    float32 ground_speed;      // renamed from speed
    float32 altitude_msl;      // renamed from altitude
    float32 heading;
    float32 latitude;
    float32 longitude;
    float32 vertical_speed;    // new in V2
    float32 airspeed;          // new in V3
    uint8 op_status;           // renamed from status
    uint8 signal_quality;      // new in V2
    uint8 satellite_count;     // new in V3
    uint8 mission_phase;       // new in V3
    uint32 sequence_number;    // new in V3
    uint8 payload[MAX_PAYLOAD_SIZE];
    BatteryInfo_t battery;     // new nested struct in V2
} TelemetryData_t;
```

### Config: one YAML file

```yaml
types:
  TelemetryData_t:
    version_macro: TELEMETRY_DATA_VERSION
    generate_reverse: true
    defaults:
      vertical_speed: "0.0"
      signal_quality: "0"
      airspeed: "0.0"
      satellite_count: "0"
      mission_phase: "0"
      sequence_number: "0"
    renames:
      speed: ground_speed
      status: op_status
      altitude: altitude_msl
    field_warnings:
      op_status:
        note: "V1-V2 uses bitmask; V3+ uses enum."
        severity: 1
```

### Output: generated converter (verbatim from golden files)

```cpp
void Converter_TelemetryData_t::convert_V1_to_Generic(
    TelemetryData_t_V_Gen::TelemetryData_t& dest,
    const TelemetryData_t_V_1::TelemetryData_t& source)
{
    memset(&dest, 0, sizeof(dest));
    dest.timestamp = source.timestamp;
    dest.ground_speed = source.speed;               // ← rename applied
    dest.altitude_msl = source.altitude;             // ← rename applied
    dest.heading = source.heading;
    dest.latitude = source.latitude;
    dest.longitude = source.longitude;
    dest.op_status = source.status;                  // ← rename applied
    for (int i = 0; i < (32 < 64 ? 32 : 64); i++)  // ← array min-copy
    {
        dest.payload[i] = source.payload[i];
    }
    dest.vertical_speed = 0.0;                       // ← default injected
    dest.signal_quality = 0;                         // ← default injected
    // Field 'battery' not in source, zero-initialized by memset
    dest.airspeed = 0.0;                             // ← default injected
    dest.satellite_count = 0;                        // ← default injected
    dest.mission_phase = 0;                          // ← default injected
    dest.sequence_number = 0;                        // ← default injected
}
```

**This compiles with `g++ -std=c++17`. This passes golden file verification.
This is zero manual converter code.**

## Architecture

```
  Versioned Headers          YAML Config
  ┌──────────────┐      ┌──────────────────┐
  │ v1/types.h   │      │ renames:         │
  │ v2/types.h   │      │   speed: g_speed │
  │ v3/types.h   │      │ defaults:        │
  └──────┬───────┘      │   airspeed: "0"  │
         │              └────────┬─────────┘
         ▼                       ▼
  ┌─────────────────────────────────────┐
  │  Parse + Preprocess                 │
  │  • Strip comments, capture #defines │
  │  • Handle #ifdef/#endif conditionals│
  │  • Tokenize + recursive descent     │
  │  • Evaluate constant expressions    │
  └──────────────┬──────────────────────┘
                 ▼
  ┌─────────────────────────────────────┐
  │  Type Registry                      │
  │  • Collect all types × all versions │
  │  • Detect version conflicts (FR-14) │
  │  • Check field-type compatibility   │
  └──────────────┬──────────────────────┘
                 ▼
  ┌─────────────────────────────────────┐
  │  Generic Hub (superset)             │
  │  • Union of all fields across vers  │
  │  • Apply renames to canonical names │
  │  • Max array dimensions             │
  └──────────────┬──────────────────────┘
                 ▼
  ┌─────────────────────────────────────┐
  │  Code Emitter (pluggable)           │
  │  • C++ classes     (default)        │
  │  • Python dataclasses               │
  │  • Shared library  (.so/.dll)       │
  └──────────────┬──────────────────────┘
                 ▼
  ┌─────────────────────────────────────┐
  │  Output                             │
  │  • data_types/<Type>.h              │
  │  • converters/generated/*.cpp       │
  │  • field_provenance.json            │
  │  • version_overview.json            │
  │  • version_negotiation.h            │
  └─────────────────────────────────────┘
```

## Ecosystem integration

ductape works with C struct headers from any source. Existing tools in many
domains already produce the headers ductape needs:

| Domain | Tool | Produces | ductape fit |
|--------|------|----------|-------------|
| MAVLink (drones) | `mavgen` | C struct headers from XML | Direct |
| Protobuf (embedded) | `nanopb` | Fixed-size C structs from .proto | Direct |
| ROS (robotics) | `rosidl_generator_c` | C structs from .msg files | Direct |
| CAN bus (automotive) | `cantools`/`dbcc` | C structs from .dbc files | With bitfield support |

ductape also has **built-in frontends** for Protobuf `.proto` and JSON Schema
files, parsing them directly without an intermediate C header step.

## Supported formats

### Parser frontends (input)

| Frontend | Format ID | Input | Status |
|----------|-----------|-------|--------|
| C headers | `c_header` | `.h` files with `typedef struct` | Default, full support |
| Protobuf | `protobuf` | `.proto` (proto2/proto3) | message, enum, repeated, map, oneof |
| JSON Schema | `json_schema` | `.json` schema (draft-07+) | object, array, $ref, enum |

### Code emitters (output)

| Emitter | Emitter ID | Output | Status |
|---------|-----------|--------|--------|
| C++ classes | `cpp` | `Converter_<Type>.h/.cpp` | Default, compiles with g++ |
| Python dataclasses | `python` | `converter_<type>.py` | Pure Python, no dependencies |
| Shared library | `shared_lib` | C source with stable ABI | `GetConverterVersion()`, `ConvertData()` |

## CLI commands

```bash
# Generate adapters
ductape generate --config CONFIG --output DIR

# Verify against golden files
ductape verify --config CONFIG --expected DIR

# Extract headers from package manager packages
ductape extract-deps --config CONFIG --output DIR

# Diff two version snapshots
ductape diff --previous OLD.json --current NEW.json

# Structural diff between generated outputs
ductape struct-diff --dir1 DIR1 --dir2 DIR2
```

Add `--no-color` to any command to disable ANSI color output.

## What gets generated

| File | Description |
|------|-------------|
| `data_types/<Type>.h` | All versions in C++ namespaces + generic superset |
| `converters/generated/Converter_<Type>.h` | Converter class declaration |
| `converters/generated/Converter_<Type>.cpp` | Field-by-field conversion implementations |
| `converters/generated/converters.cpp` | Factory registration (`GetGeneratedAdapters()`) |
| `converters/generated/version_negotiation.h` | Runtime version query + negotiation helpers |
| `field_provenance.json` | Cross-version field audit trail |
| `version_overview.json` | Active version numbers per type |

## Configuration reference

```yaml
project:
  name: my_project
  generic_version_sentinel: 9999      # Hub version number (don't use as real version)

format: c_header                       # Parser frontend: c_header | protobuf | json_schema
emitter: cpp                           # Code emitter: cpp | python | shared_lib

header_sources:
  - path: "headers/v1"                 # Directory containing .h files
    version_tag: "v1"
  - path: "headers/v2"
    version_tag: "v2"

additional_includes:
  - "headers"                          # Platform type headers (uint8, float32, etc.)

types:
  TelemetryData_t:
    version_macro: TELEMETRY_DATA_VERSION   # #define that holds the version number
    generate_reverse: true                  # Generate Generic→V_N converters
    defaults:                               # Values for fields missing in older versions
      airspeed: "0.0"
      satellite_count: "0"
    renames:                                # Field name evolution: old → new
      speed: ground_speed
      altitude: altitude_msl
    enum_mappings:                          # Enum value remapping between versions
      status:
        OLD_ACTIVE: NEW_RUNNING
        OLD_IDLE: NEW_STANDBY
    field_warnings:                         # Semantic notes for the audit trail
      op_status:
        note: "Bitmask in V1-V2, enum in V3+"
        severity: 1

warnings:
  min_display_severity: 1              # 0=info, 1=warning, 2=error
  color: true
```

## Limitations

**Parser:**
- C `typedef struct`, `typedef union`, `typedef enum`, `#define`, `#ifdef`/`#endif`
- Does **not** support: function pointers, C++ classes/templates/namespaces, complex macros
- `__attribute__((...))` and type qualifiers (`const`, `volatile`, `static`, `restrict`) are gracefully skipped

**Emitters:**
- Rust emitter not yet implemented (plugin architecture ready)
- Python emitter generates code but doesn't handle nested struct copying

**General:**
- No wire-format encoding/decoding — ductape is a schema-level adapter, not a serialization library
- Tested at 50 types × 5 versions (compiles, generates correctly); not stress-tested beyond that

## Prior art

| System | Approach | How ductape differs |
|--------|----------|-------------------|
| Apache Avro | Runtime schema resolution (reader + writer schemas) | ductape generates compile-time converters |
| ROS rosbag migration | Semi-manual Python migration rules | ductape is fully automatic from YAML config |
| Linux kernel `copy_struct_from_user()` | Runtime size-based zero-extension | ductape handles renames, defaults, array resizing |
| Protobuf/FlatBuffers | Wire format designed for version tolerance | ductape works with raw C structs (no wire format) |

## Repository structure

```
ductape/
├── pyproject.toml
├── ductape/                          Python package
│   ├── cli.py                        CLI dispatch
│   ├── codegen.py                    Generation driver
│   ├── config.py                     YAML config loader
│   ├── warnings.py                   Diagnostic collector
│   ├── dependency_extractor.py       Package manager header extraction
│   ├── version_diff.py               Version snapshot diffing
│   ├── struct_diff.py                Structural output diffing
│   ├── two_stage.py                  Two-stage adaptation pipeline
│   ├── conv/                         Core parsing + generation engine
│   │   ├── preprocessor.py           #define, #ifdef, comment stripping
│   │   ├── expression_eval.py        Constant expression evaluator
│   │   ├── tokenizer.py              Lexer
│   │   ├── parser.py                 Recursive-descent C parser
│   │   ├── typecontainer.py          AST model (CType, CTypeMember)
│   │   ├── type_registry.py          Multi-version type collector
│   │   ├── data_type.py              Logical type across versions
│   │   ├── converter.py              Field-level conversion generator
│   │   ├── code_writer.py            Indented code writer
│   │   └── field_provenance.py       Audit report generator
│   ├── frontends/                    Parser frontends (pluggable)
│   │   ├── frontend_base.py          Abstract interface + registry
│   │   ├── c_header.py               C header parser
│   │   ├── protobuf.py               Protobuf .proto parser
│   │   └── json_schema.py            JSON Schema parser
│   └── emitters/                     Code emitters (pluggable)
│       ├── emitter_base.py           Abstract interface + registry
│       ├── cpp_emitter.py            C++ class emitter
│       ├── python_emitter.py         Python dataclass emitter
│       └── shared_lib_emitter.py     Shared library (.so/.dll) emitter
├── variants/
│   ├── reference_project/            Reference: 3 types × 3 versions
│   │   ├── config.yaml
│   │   ├── headers/v1/ v2/ v3/
│   │   └── expected_output/
│   └── reference_multi_format/       Multi-format example (Protobuf + JSON)
├── runtime_reference/                Minimal adapter runtime headers
├── tests/                            179 tests across 15 test files
└── docs/
    ├── architecture.md               Full specification (27 FRs)
    ├── build-phases.md               Build plan (Phases 1-14)
    └── requirements-status.md        35/35 requirements MET
```

## Test coverage

```
179 tests across 15 test files
├── Core: parser, tokenizer, preprocessor, expressions        34 tests
├── Generation: converters, golden files, config               19 tests
├── Phase 11: warnings, versioning, deps, diff                 21 tests
├── Phase 12: plugin architecture                              16 tests
├── Phase 13: Protobuf + JSON Schema                           19 tests
├── Phase 14: shared lib, two-stage, struct-diff               18 tests
├── Limitation fixes: unions, #ifdef, qualifiers, enum map,
│   Python emitter, version negotiation, scale test            26 tests
└── Pointer abstractions, semantic conflicts                   26 tests
```

All tests pass. Generated C++ compiles with `g++ -std=c++17`. Scale test
validates 50 types × 5 versions generating and compiling correctly.

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Requirements coverage

All **35 requirements** (27 functional + 8 non-functional) are **MET**.
See [requirements-status.md](docs/requirements-status.md) for the full table.

## License

See repository for license information.
