# ductape — Build Phases

Each phase has acceptance criteria. Do NOT move to the next phase until the
current phase's criteria all pass. Run tests after every phase.

---

## Phase 1: Project skeleton + sample headers
Create the full directory structure. Create pyproject.toml with:
- name: ductape
- CLI entry point: ductape → ductape.cli:main
- dependencies: [pyyaml]
- dev dependencies: [pytest]

Create 3 versions of telemetry structs in variants/reference_project/headers/:
- v1/telemetry_types.h: TelemetryData_t (V1), CommandMessage_t (V1), SystemStatus_t (V1)
- v2/telemetry_types.h: Same types V2 — added fields (BatteryInfo_t, signal_quality, vertical_speed), payload array 32→64
- v3/telemetry_types.h: Same types V3 — renamed fields (speed→ground_speed, status→op_status, altitude→altitude_msl), added airspeed, satellite_count, mission_phase, sequence_number
- headers/platform_types.h: uint8, uint16, uint32, sint8, float32, float64 etc.

Create runtime_reference/adapter_base.h and version_info.h (minimal, compilable).
Create variants/reference_project/config.yaml per §6.7.1 of spec.
Create all __init__.py files. Create empty test files.

**Acceptance:** `pip install -e .` succeeds. `ductape --help` runs. Directory structure matches spec §5.

---

## Phase 2: Preprocessor + expression evaluator
Build and test:
1. conv/preprocessor.py — strip comments (// and /* */), capture #defines, handle multiline
2. conv/expression_eval.py — evaluate constant integer expressions: + - * / % & | ^ ~ << >> (), constant substitution from symbol table
3. tests/test_preprocessor.py — ≥8 test cases
4. tests/test_expression_eval.py — ≥8 test cases

**Acceptance:** `pytest tests/test_preprocessor.py tests/test_expression_eval.py -v` all green.

---

## Phase 3: Tokenizer + TypeContainer + parser
Build and test:
1. conv/tokenizer.py — Token types: Symbol, Integer, Float, String, Special, Operator, EOF
2. conv/typecontainer.py — CType dataclass, TypeContainer with basictypes/types/defines/namespaces
3. conv/parser.py — Recursive descent: typedef struct, typedef enum, typedef alias, nested structs, arrays, bitfields, C++ style struct Name {}, tagged typedefs
4. tests/test_tokenizer.py — ≥8 tests
5. tests/test_parser.py — ≥10 tests including nested structs, arrays, enums

Verify: parse all 3 header versions and confirm all structs + defines captured.

**Acceptance:** `pytest tests/test_tokenizer.py tests/test_parser.py -v` all green. All 3 header versions parse without error. TelemetryData_t has correct member count in each version.

---

## Phase 4: Config + type registry
Build and test:
1. config.py — YAML loader with validation (required fields: project, header_sources, types)
2. conv/interface_version.py — parse one header at one version → TypeContainer
3. conv/data_type.py — one logical type across versions
4. conv/data_type_version.py — one (type, version) tuple
5. conv/type_registry.py — registry that collects all types from all versions
6. tests/test_config_validation.py — ≥6 tests (valid, missing fields, bad types)

**Acceptance:** `pytest tests/test_config_validation.py -v` all green. Can load config.yaml and parse all header versions into a TypeRegistry.

---

## Phase 5: Pointer abstractions
Build and test:
1. conv/pointers/struct_pointer.py — 3-step fuzzy lookup + AmbiguousMemberError
2. conv/pointers/value_pointer.py — navigate default value trees
3. conv/pointers/warning_null_pointer.py — null-safe fallback
4. conv/source_container.py — priority-ranked pointer list
5. conv/value_container.py — ValueObject tree

**Acceptance:** Unit tests for struct_pointer (exact match, fuzzy match, ambiguity error) pass.

---

## Phase 6: Code generation (THE CRITICAL PHASE)
This is the hardest phase. Build carefully:
1. conv/code_writer.py — C++ file writer with indent tracking
2. conv/converter.py — field-level C++ conversion function body generation:
   - Field-by-field copy with name matching
   - Default value injection for missing fields
   - Array min-dimension copy: `for (int i = 0; i < min(src_dim, dst_dim); i++)`
   - Rename handling via config renames
   - Skip generation when src and dst are structurally identical
3. ductape/codegen.py — top-level driver: iterate types, generate:
   - data_types/<TypeName>.h (all versions in namespaces + generic)
   - converters/generated/Converter_<TypeName>.h and .cpp
   - converters/generated/converters.cpp (factory)
4. tests/test_converter_generation.py — ≥8 tests

IMPORTANT: Generated C++ must include:
- `#pragma once` headers
- `#include "platform_types.h"` in data_types headers
- `static_assert(VERSION_MACRO != 9999, ...)` sentinel guard
- `memset(&dest, 0, sizeof(dest))` at start of each converter
- Proper namespace qualification on all types
- Real field-by-field assignment, NOT memcpy

**Acceptance:** `ductape generate --config variants/reference_project/config.yaml --output build/` runs clean. Generated files exist. `g++ -c build/converters/generated/*.cpp -Ibuild/data_types -Iruntime_reference -std=c++17` compiles with ZERO errors.

---

## Phase 7: Warnings + field provenance
1. ductape/warnings.py — WarningModule with severity levels 0/1/2, colored output, --no-color
2. conv/field_provenance.py — generate field_provenance.json
3. Semantic conflict detection in type_registry merge
4. tests/test_semantic_conflicts.py — ≥4 tests

**Acceptance:** build/field_provenance.json exists and contains entries for all 3 types with correct version mappings.

---

## Phase 8: CLI wiring
Wire cli.py with subcommands:
- `ductape generate --config CONFIG --output DIR`
- `ductape verify --config CONFIG --expected DIR`
Run full pipeline end-to-end.

**Acceptance:** Both commands work. Generate produces all expected files.

---

## Phase 9: Golden files + verify
1. Run generator, copy output to variants/reference_project/expected_output/
2. Implement verify command (file-by-file comparison)
3. tests/test_golden_files.py
4. `ductape verify` passes

**Acceptance:** `ductape verify --config variants/reference_project/config.yaml --expected variants/reference_project/expected_output/` exits 0.

---

## Phase 10: Final acceptance
Run ALL checks. Do not stop until every single one passes:

```bash
pytest tests/ -v                          # ALL green
ductape generate --config variants/reference_project/config.yaml --output build/   # no errors
test -f build/field_provenance.json       # exists
g++ -c build/converters/generated/*.cpp -Ibuild/data_types -Iruntime_reference -std=c++17  # compiles
ductape verify --config variants/reference_project/config.yaml --expected variants/reference_project/expected_output/  # passes
```

If any check fails, fix it and re-run ALL checks from the top.
