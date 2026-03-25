# ductape — Requirements Status

Tracking document for all functional (FR) and non-functional (NFR) requirements
from the [architecture specification](architecture.md).

Last updated: 2026-03-25

---

## Functional Requirements

### Core Engine (Phases 1-10) — COMPLETE

| ID | Requirement | Status | Implementation |
|----|-------------|--------|----------------|
| FR-01 | Parse C struct headers without full compiler | **MET** | `conv/parser.py`, `conv/preprocessor.py` |
| FR-02 | Multiple versions as C++ namespaces (`TypeName_V_<N>`) | **MET** | `codegen.py` generates namespaced headers |
| FR-03 | Generic hub version (sentinel 9999 in C++) | **MET** | `data_type.py` (`GenericVersion`), `_V_Gen` namespace |
| FR-04 | Field-level V->Generic conversion functions | **MET** | `conv/converter.py` field-by-field copy |
| FR-05 | Default values for missing fields from config | **MET** | Config `defaults:`, applied in `converter.py` |
| FR-06 | Array min-dimension copy | **MET** | `for (i < min(src, dst))` pattern in converter |
| FR-07 | Field renames via config directives | **MET** | Config `renames:`, handled in `converter.py` |
| FR-08 | Skip structurally identical converters | **MET** | `are_structurally_identical()` in `converter.py` |
| FR-09 | Factory registration function | **MET** | `converters.cpp` with `GetGeneratedAdapters()` |
| FR-15 | Installable as reusable Python package | **MET** | `pyproject.toml`, `pip install -e .` |
| FR-16 | Reverse converters (Generic->V) when configured | **MET** | `generate_reverse: true` in config |
| FR-17 | Evaluate constant integer expressions in #define | **MET** | `conv/expression_eval.py` |
| FR-18 | Ambiguity error on fuzzy multi-match | **MET** | `AmbiguousMemberError` in `struct_pointer.py` |
| FR-19 | C++ structs, tagged typedefs, forward decls | **MET** | `conv/parser.py` handles all variants |
| FR-20 | Field-type compatibility checks + field_warnings | **MET** | `type_registry.py` `_check_field_compatibility()` |
| FR-21 | `field_provenance.json` report | **MET** | `conv/field_provenance.py` |

### Utility Features — NOT YET IMPLEMENTED

| ID | Requirement | Status | Planned Phase |
|----|-------------|--------|---------------|
| FR-10 | Extract headers from package manager packages | **NOT MET** | Phase 11 |
| FR-11 | Version overview CSV/JSON | **NOT MET** | Phase 11 |
| FR-12 | Diff report between version snapshots | **NOT MET** | Phase 11 |
| FR-13 | Warn (not fail) on missing source fields with severity | **PARTIAL** | Phase 11 |
| FR-14 | Detect version conflicts (same version#, different layout) | **NOT MET** | Phase 11 |

**FR-13 detail:** `WarningModule` with severity levels exists in `warnings.py`.
Defaults are applied for missing fields. Missing: active warning emission during
conversion generation when a source field is absent.

### Pluggable Architecture — NOT YET IMPLEMENTED

| ID | Requirement | Status | Planned Phase |
|----|-------------|--------|---------------|
| FR-22 | Pluggable parser frontends | **NOT MET** | Phase 12 |
| FR-23 | Protobuf `.proto` parsing | **NOT MET** | Phase 13 |
| FR-24 | JSON Schema parsing | **NOT MET** | Phase 13 |
| FR-25 | Pluggable code emitter backends | **NOT MET** | Phase 12 |
| FR-26 | Shared library `.so/.dll` emitter | **NOT MET** | Phase 14 |
| FR-27 | Two-stage adaptation pipelines | **NOT MET** | Phase 14 |

---

## Non-Functional Requirements

| ID | Requirement | Status | Implementation |
|----|-------------|--------|----------------|
| NFR-01 | Cross-platform (Win/Linux/Mac) | **MET** | Pure Python, no OS-specific logic |
| NFR-02 | Standalone CLI (`python -m ductape`) | **MET** | `__main__.py` + `cli.py` entry point |
| NFR-03 | Consistent 2-space C++ indentation via CodeWriter | **MET** | `conv/code_writer.py` |
| NFR-04 | No network access during generation | **MET** | All local file I/O |
| NFR-05 | Coloured output with `--no-color` fallback | **PARTIAL** | `WarningModule` supports color; `--no-color` CLI flag missing |
| NFR-06 | Extensible via `variants/<project>/` folders | **MET** | Config-driven, no engine changes needed |
| NFR-07 | YAML config with validation + actionable errors | **MET** | `config.py` with `ConfigError` |
| NFR-08 | Golden-file regression (`--verify`) | **MET** | `ductape verify` command |

---

## Summary

| Category | Met | Partial | Not Met | Total |
|----------|-----|---------|---------|-------|
| FR (Core Engine) | 16 | 0 | 0 | 16 |
| FR (Utility) | 0 | 1 | 4 | 5 |
| FR (Pluggable) | 0 | 0 | 6 | 6 |
| NFR | 7 | 1 | 0 | 8 |
| **Total** | **23** | **2** | **10** | **35** |

---

## Planned Future Phases

### Phase 11: Utility features (FR-10, FR-11, FR-12, FR-13, FR-14)
- `dependency_extractor.py` — extract headers from package manager packages
- `version_overview.json` — active version numbers per type
- `version_diff.py` — diff report between version snapshots
- Wire `WarningModule` into converter generation for missing-field warnings
- Version conflict detection in `type_registry.py` (same version#, different layout)
- Add `--no-color` CLI flag (NFR-05)

### Phase 12: Pluggable architecture (FR-22, FR-25)
- `frontends/frontend_base.py` — abstract `ParserFrontend` interface
- `frontends/c_header.py` — wrap existing parser as a frontend
- `emitters/emitter_base.py` — abstract `CodeEmitter` interface
- `emitters/cpp_emitter.py` — wrap existing C++ generation as an emitter

### Phase 13: Additional format support (FR-23, FR-24)
- `frontends/protobuf.py` — Protobuf `.proto` parser -> TypeContainer
- `frontends/json_schema.py` — JSON Schema parser -> TypeContainer

### Phase 14: Advanced emitters + two-stage (FR-26, FR-27)
- `emitters/shared_lib_emitter.py` — `.so/.dll` with C ABI and `GetConverterVersion()`
- Two-stage adaptation pipeline configuration and execution
