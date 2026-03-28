"""Tests for limitation fixes: unions, #ifdef, qualifiers, enum mapping, Python emitter, scale."""

import os
import json
import tempfile
import pytest

from ductape.conv.parser import Parser
from ductape.conv.preprocessor import Preprocessor
from ductape.conv.typecontainer import TypeContainer
from ductape.conv.code_writer import CodeWriter
from ductape.conv.converter import Converter
from ductape.conv.data_type import DataType
from ductape.conv.data_type_version import DataTypeVersion
from ductape.conv.typecontainer import CType, CTypeMember
from ductape.codegen import run_generate
from ductape.emitters.emitter_base import get_emitter, list_emitters


def _ref_config_path():
    return os.path.join(os.path.dirname(__file__), "..",
                        "variants/reference_project/config.yaml")


# ── Union support ──────────────────────────────────────────────────


def test_parse_typedef_union():
    """Parser handles typedef union definitions."""
    parser = Parser()
    container = parser.parse("""
typedef union {
    uint32 as_int;
    float32 as_float;
    uint8 as_bytes[4];
} DataUnion_t;
""")
    assert "DataUnion_t" in container.types
    ut = container.types["DataUnion_t"]
    assert ut.is_union
    assert len(ut.members) == 3
    names = [m.name for m in ut.members]
    assert "as_int" in names
    assert "as_float" in names
    assert "as_bytes" in names


def test_parse_cpp_style_union():
    """Parser handles C++ style union Name { ... };"""
    parser = Parser()
    container = parser.parse("""
union Variant {
    uint32 integer;
    float64 floating;
};
""")
    assert "Variant" in container.types
    assert container.types["Variant"].is_union


def test_parse_tagged_typedef_union():
    """Parser handles typedef union Tag { ... } Name;"""
    parser = Parser()
    container = parser.parse("""
typedef union _data_u {
    uint32 val;
    uint8 bytes[4];
} DataU_t;
""")
    assert "DataU_t" in container.types
    assert container.types["DataU_t"].is_union


def test_parse_union_member_in_struct():
    """Parser handles union member inside struct."""
    parser = Parser()
    container = parser.parse("""
typedef union {
    uint32 as_int;
    float32 as_float;
} ValueUnion_t;

typedef struct {
    uint32 type_tag;
    ValueUnion_t value;
} TaggedValue_t;
""")
    assert "ValueUnion_t" in container.types
    assert "TaggedValue_t" in container.types
    tv = container.types["TaggedValue_t"]
    assert len(tv.members) == 2


# ── #ifdef / #ifndef / #endif support ──────────────────────────────


def test_ifdef_includes_defined_block():
    """#ifdef includes block when symbol is defined."""
    pp = Preprocessor()
    pp.defines["FEATURE_X"] = ""
    result = pp.process("""
#ifdef FEATURE_X
uint32 included_line;
#endif
""")
    assert "included_line" in result


def test_ifdef_excludes_undefined_block():
    """#ifdef excludes block when symbol is not defined."""
    pp = Preprocessor()
    result = pp.process("""
#ifdef NONEXISTENT
uint32 excluded_line;
#endif
uint32 visible_line;
""")
    assert "excluded_line" not in result
    assert "visible_line" in result


def test_ifndef_includes_undefined():
    """#ifndef includes block when symbol is NOT defined."""
    pp = Preprocessor()
    result = pp.process("""
#ifndef GUARD_H
#define GUARD_H
uint32 guarded_content;
#endif
""")
    assert "guarded_content" in result


def test_ifdef_else_branch():
    """#ifdef/#else correctly selects branch."""
    pp = Preprocessor()
    pp.defines["USE_V2"] = ""
    result = pp.process("""
#ifdef USE_V2
uint32 v2_field;
#else
uint32 v1_field;
#endif
""")
    assert "v2_field" in result
    assert "v1_field" not in result


def test_ifdef_nested():
    """Nested #ifdef blocks work correctly."""
    pp = Preprocessor()
    pp.defines["OUTER"] = ""
    result = pp.process("""
#ifdef OUTER
uint32 outer_visible;
#ifdef INNER
uint32 inner_hidden;
#endif
#endif
""")
    assert "outer_visible" in result
    assert "inner_hidden" not in result


def test_ifdef_with_define_in_block():
    """#define inside #ifdef block is captured."""
    pp = Preprocessor()
    pp.defines["FEATURE"] = ""
    result = pp.process("""
#ifdef FEATURE
#define VERSION 5
uint32 field;
#endif
""")
    assert "VERSION" in pp.defines
    assert pp.defines["VERSION"] == "5"


def test_parser_with_ifdef_guards():
    """Full parser handles header with #ifdef include guards."""
    parser = Parser()
    container = parser.parse("""
#ifndef MY_HEADER_H
#define MY_HEADER_H

typedef struct {
    uint32 x;
    uint32 y;
} Point_t;

#endif
""")
    assert "Point_t" in container.types
    assert len(container.types["Point_t"].members) == 2


# ── Qualifier and __attribute__ support ────────────────────────────


def test_parse_static_qualifier():
    """Parser handles static qualifier on struct members."""
    parser = Parser()
    container = parser.parse("""
typedef struct {
    static uint32 count;
    uint32 value;
} MyType_t;
""")
    # static is skipped, member parsed
    assert "MyType_t" in container.types


def test_parse_restrict_qualifier():
    """Parser handles restrict qualifier."""
    parser = Parser()
    container = parser.parse("""
typedef struct {
    restrict uint32 data;
    uint32 other;
} RestrictType_t;
""")
    assert "RestrictType_t" in container.types


def test_parse_attribute_packed():
    """Parser skips __attribute__((packed)) on structs."""
    parser = Parser()
    container = parser.parse("""
typedef struct {
    uint32 a;
    uint8 b;
} __attribute__((packed)) PackedType_t;
""")
    assert "PackedType_t" in container.types
    assert len(container.types["PackedType_t"].members) == 2


def test_parse_attribute_on_member():
    """Parser skips __attribute__ on struct members."""
    parser = Parser()
    container = parser.parse("""
typedef struct {
    __attribute__((aligned(4))) uint32 aligned_field;
    uint32 normal_field;
} AlignedType_t;
""")
    assert "AlignedType_t" in container.types
    assert len(container.types["AlignedType_t"].members) == 2


def test_parse_attribute_at_top_level():
    """Parser skips top-level __attribute__."""
    parser = Parser()
    container = parser.parse("""
__attribute__((visibility("default")))
typedef struct {
    uint32 x;
} VisibleType_t;
""")
    assert "VisibleType_t" in container.types


# ── Enum value remapping ───────────────────────────────────────────


def test_enum_mapping_in_converter():
    """Converter generates switch/case for enum-mapped fields."""
    # Create a simple type with enum_mappings
    ctype_v1 = CType(name="Status_t", is_struct=True, members=[
        CTypeMember(name="state", type_name="uint8", is_basic_type=True),
    ])
    ctype_gen = CType(name="Status_t", is_struct=True, members=[
        CTypeMember(name="state", type_name="uint8", is_basic_type=True),
    ])

    dt = DataType(
        name="Status_t",
        version_macro="STATUS_VERSION",
        enum_mappings={"state": {"0": "10", "1": "20", "2": "30"}},
    )
    dt.add_version(1, ctype_v1)
    dtv_gen = DataTypeVersion(type_name="Status_t", version=9999,
                              ctype=ctype_gen, namespace="Status_t_V_Gen")
    dt.generic = dtv_gen

    config = {"project": {"generic_version_sentinel": 9999}}
    conv = Converter(dt, config)

    w = CodeWriter()
    conv.generate_forward_body(dt.versions[1], w)
    output = w.get_content()

    assert "switch (source.state)" in output
    assert "case 0: dest.state = 10; break;" in output
    assert "case 1: dest.state = 20; break;" in output
    assert "default: dest.state = source.state; break;" in output


def test_no_enum_mapping_uses_direct_copy():
    """Without enum_mappings, fields are copied directly."""
    ctype_v1 = CType(name="Simple_t", is_struct=True, members=[
        CTypeMember(name="value", type_name="uint32", is_basic_type=True),
    ])
    ctype_gen = CType(name="Simple_t", is_struct=True, members=[
        CTypeMember(name="value", type_name="uint32", is_basic_type=True),
    ])

    dt = DataType(name="Simple_t", version_macro="SIMPLE_VERSION")
    dt.add_version(1, ctype_v1)
    dt.generic = DataTypeVersion(type_name="Simple_t", version=9999,
                                 ctype=ctype_gen, namespace="Simple_t_V_Gen")

    config = {"project": {"generic_version_sentinel": 9999}}
    conv = Converter(dt, config)

    w = CodeWriter()
    conv.generate_forward_body(dt.versions[1], w)
    output = w.get_content()

    assert "dest.value = source.value;" in output
    assert "switch" not in output


# ── Python emitter ─────────────────────────────────────────────────


def test_python_emitter_registered():
    """PythonEmitter is auto-registered."""
    assert "python" in list_emitters()


def test_python_emitter_generates_types():
    """PythonEmitter generates dataclass type files."""
    from ductape.config import load_config
    from ductape.conv.type_registry import TypeRegistry

    config = load_config(_ref_config_path())
    registry = TypeRegistry(config)
    registry.load_all()
    emitter = get_emitter("python")

    with tempfile.TemporaryDirectory() as tmpdir:
        for dt in registry.data_types.values():
            emitter.emit_type_header(dt, tmpdir)

        # Check files exist
        types_dir = os.path.join(tmpdir, "types")
        assert os.path.isdir(types_dir)
        assert os.path.isfile(os.path.join(types_dir, "TelemetryData_t.py"))

        # Check content is valid Python syntax
        with open(os.path.join(types_dir, "TelemetryData_t.py")) as f:
            content = f.read()
        assert "@dataclass" in content
        assert "class TelemetryData_t_V1:" in content
        assert "class TelemetryData_t_Generic:" in content
        assert "timestamp: int" in content


def test_python_emitter_generates_converters():
    """PythonEmitter generates converter function files."""
    from ductape.config import load_config
    from ductape.conv.type_registry import TypeRegistry

    config = load_config(_ref_config_path())
    registry = TypeRegistry(config)
    registry.load_all()
    emitter = get_emitter("python")

    with tempfile.TemporaryDirectory() as tmpdir:
        for dt in registry.data_types.values():
            emitter.emit_converter(dt, config, tmpdir)

        conv_dir = os.path.join(tmpdir, "converters")
        assert os.path.isdir(conv_dir)
        conv_file = os.path.join(conv_dir, "converter_TelemetryData_t.py")
        assert os.path.isfile(conv_file)

        with open(conv_file) as f:
            content = f.read()
        assert "def convert_TelemetryData_t_V1_to_Generic" in content
        assert "dest.ground_speed = source.speed" in content  # rename handling


def test_python_emitter_generates_registry():
    """PythonEmitter generates converter registry."""
    from ductape.config import load_config
    from ductape.conv.type_registry import TypeRegistry

    config = load_config(_ref_config_path())
    registry = TypeRegistry(config)
    registry.load_all()
    emitter = get_emitter("python")

    with tempfile.TemporaryDirectory() as tmpdir:
        emitter.emit_factory(registry.data_types, tmpdir)

        reg_file = os.path.join(tmpdir, "converters", "registry.py")
        assert os.path.isfile(reg_file)

        with open(reg_file) as f:
            content = f.read()
        assert "CONVERTERS" in content
        assert '"TelemetryData_t"' in content


# ── Runtime version negotiation ────────────────────────────────────


def test_version_negotiation_header_generated():
    """CppEmitter generates version_negotiation.h."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_generate(_ref_config_path(), tmpdir)

        neg_file = os.path.join(tmpdir, "converters", "generated",
                                "version_negotiation.h")
        assert os.path.isfile(neg_file)

        with open(neg_file) as f:
            content = f.read()

        assert "namespace ductape" in content
        assert "GetSupportedVersions" in content
        assert "GetLatestVersion" in content
        assert "NegotiateBestVersion" in content


def test_version_negotiation_compiles():
    """version_negotiation.h compiles as part of the generated output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_generate(_ref_config_path(), tmpdir)

        # Create a small test file that includes the negotiation header
        test_cpp = os.path.join(tmpdir, "test_negotiation.cpp")
        with open(test_cpp, 'w') as f:
            f.write('#include "converters/generated/version_negotiation.h"\n')
            f.write('int main() {\n')
            f.write('  auto v = ductape::TelemetryData_t_GetSupportedVersions();\n')
            f.write('  return v.empty() ? 1 : 0;\n')
            f.write('}\n')

        ret = os.system(
            f"g++ {test_cpp} -I{tmpdir} -std=c++17 -o /dev/null 2>/dev/null"
        )
        assert ret == 0


# ── Scale stress test ──────────────────────────────────────────────


def test_scale_50_types_5_versions():
    """Generate adapters for 50 types × 5 versions and verify pipeline works."""
    import yaml

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create headers directory
        headers_dir = os.path.join(tmpdir, "headers")
        os.makedirs(headers_dir)

        # Create platform_types.h
        with open(os.path.join(headers_dir, "platform_types.h"), 'w') as f:
            f.write("""
typedef unsigned char uint8;
typedef unsigned short uint16;
typedef unsigned int uint32;
typedef float float32;
typedef double float64;
""")

        num_types = 50
        num_versions = 5
        types_config = {}

        for v in range(1, num_versions + 1):
            ver_dir = os.path.join(headers_dir, f"v{v}")
            os.makedirs(ver_dir)
            header_lines = [
                f'#include "platform_types.h"',
                "",
            ]
            for t in range(num_types):
                type_name = f"Type{t:03d}_t"
                macro_name = f"TYPE{t:03d}_VERSION"
                header_lines.append(f"#define {macro_name} {v}")
                header_lines.append(f"typedef struct {{")
                # Base fields present in all versions
                header_lines.append(f"  uint32 id;")
                header_lines.append(f"  uint32 timestamp;")
                header_lines.append(f"  float32 value;")
                # Add version-specific fields
                for extra in range(v):
                    header_lines.append(f"  uint32 field_v{extra + 1};")
                header_lines.append(f"}} {type_name};")
                header_lines.append("")

                if v == 1:
                    types_config[type_name] = {
                        "version_macro": macro_name,
                    }

            with open(os.path.join(ver_dir, "types.h"), 'w') as f:
                f.write('\n'.join(header_lines))

        # Create config
        config = {
            "project": {"name": "scale_test"},
            "header_sources": [
                {"path": f"headers/v{v}", "version_tag": f"v{v}"}
                for v in range(1, num_versions + 1)
            ],
            "additional_includes": ["headers"],
            "types": types_config,
        }

        config_path = os.path.join(tmpdir, "config.yaml")
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        # Run generation
        output_dir = os.path.join(tmpdir, "output")
        run_generate(config_path, output_dir)

        # Verify output
        overview_path = os.path.join(output_dir, "version_overview.json")
        assert os.path.isfile(overview_path)
        with open(overview_path) as f:
            overview = json.load(f)

        assert len(overview) == num_types
        for t in range(num_types):
            type_name = f"Type{t:03d}_t"
            assert type_name in overview
            assert overview[type_name]["version_count"] == num_versions

        # Verify compilation
        ret = os.system(
            f"g++ -c {output_dir}/converters/generated/*.cpp "
            f"-I{output_dir} -Iruntime_reference "
            f"-I{output_dir}/converters/generated -std=c++17 2>/dev/null"
        )
        assert ret == 0, "Scale test: generated C++ should compile"


# ── Existing pipeline unaffected ───────────────────────────────────


def test_existing_golden_files_still_match():
    """Golden file verification still passes with all enhancements."""
    from ductape.codegen import run_verify
    run_verify(
        _ref_config_path(),
        os.path.join(os.path.dirname(__file__), "..",
                     "variants/reference_project/expected_output"),
    )
