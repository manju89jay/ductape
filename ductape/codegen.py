"""Generation driver - top-level orchestrator."""

import os
import json
from ductape.config import load_config
from ductape.conv.type_registry import TypeRegistry
from ductape.conv.code_writer import CodeWriter
from ductape.conv.converter import Converter
from ductape.warnings import WarningModule

# Import frontends and emitters to trigger registration
import ductape.frontends.c_header  # noqa: F401
import ductape.emitters.cpp_emitter  # noqa: F401


def run_generate(config_path, output_dir, use_color=True):
    """Run the full generation pipeline."""
    config = load_config(config_path)
    registry = TypeRegistry(config)
    registry.load_all()

    sentinel = config['project'].get('generic_version_sentinel', 9999)

    # Create warning module (FR-13)
    warn_cfg = config.get('warnings', {})
    warning_module = WarningModule(
        min_severity=warn_cfg.get('min_display_severity', 1),
        use_color=use_color and warn_cfg.get('color', True),
    )

    os.makedirs(output_dir, exist_ok=True)

    # Select emitter based on config (FR-25), default to cpp
    emitter_id = config.get('emitter', 'cpp')
    emitter = _get_emitter(emitter_id)

    if emitter:
        # Use pluggable emitter
        for type_name, dt in registry.data_types.items():
            emitter.emit_type_header(dt, output_dir, registry=registry)
        for type_name, dt in registry.data_types.items():
            emitter.emit_converter(dt, config, output_dir, warning_module=warning_module)
        emitter.emit_factory(registry.data_types, output_dir)
        emitter.emit_platform_types(config, output_dir)
    else:
        # Fallback to built-in generation
        for type_name, dt in registry.data_types.items():
            _generate_data_type_header(dt, sentinel, output_dir, registry)
        for type_name, dt in registry.data_types.items():
            _generate_converter(dt, config, output_dir, warning_module)
        _generate_factory(registry.data_types, output_dir)
        _copy_platform_types(config, output_dir)

    # Generate field provenance
    _generate_field_provenance(registry, output_dir)

    # Generate version overview (FR-11)
    _generate_version_overview(registry, output_dir)

    # Display warnings (FR-13)
    if warning_module.count() > 0:
        warning_module.display()

    print(f"Generation complete. Output in {output_dir}")


def _get_emitter(emitter_id):
    """Get emitter by ID, returning None if not found (falls back to built-in)."""
    from ductape.emitters.emitter_base import get_emitter
    try:
        return get_emitter(emitter_id)
    except ValueError:
        return None


def _generate_data_type_header(dt, sentinel, output_dir, registry):
    """Generate data_types/<TypeName>.h with all version namespaces."""
    w = CodeWriter()
    w.line("#pragma once")
    w.line('#include "platform_types.h"')
    w.line()

    # Static assert guard - only active when the version macro is defined
    w.line(f"#ifdef {dt.version_macro}")
    w.line(f"static_assert({dt.version_macro} != {sentinel},")
    w.line(f'  "Version {sentinel} is reserved as the generic adapter hub version");')
    w.line(f"#endif")
    w.line()

    # Get all version containers for struct member type resolution
    all_versions = sorted(dt.versions.keys())

    # Generate namespace for each version
    for ver_num in all_versions:
        dtv = dt.versions[ver_num]
        _generate_version_namespace(w, dt, dtv, ver_num, registry)

    # Generate generic version namespace
    if dt.generic:
        _generate_version_namespace(w, dt, dt.generic, sentinel, registry, is_generic=True)

    filepath = os.path.join(output_dir, "data_types", f"{dt.name}.h")
    w.write_to(filepath)


def _generate_version_namespace(w, dt, dtv, version, registry, is_generic=False):
    """Generate one namespace block for a version."""
    ns = dtv.namespace
    w.block_open(f"namespace {ns}")
    w.line(f"static const uint32_t VERSION = {version};")

    # Check if we need to emit dependent struct types (like BatteryInfo_t)
    # that are used as member types
    emitted_types = set()
    _emit_dependent_types(w, dtv, dt.name, emitted_types, registry)

    w.line()
    w.line(f"typedef struct")
    w.block_open()
    for member in dtv.ctype.members:
        dim_str = ''.join(f'[{d}]' for d in member.dimensions)
        w.line(f"{member.type_name} {member.name}{dim_str};")
    w.block_close(f" {dt.name};")
    w.block_close(f" // namespace {ns}")
    w.line()


def _emit_dependent_types(w, dtv, parent_name, emitted, registry):
    """Emit struct types used as members that aren't the parent type."""
    for member in dtv.ctype.members:
        type_name = member.type_name
        if type_name == parent_name or type_name in emitted:
            continue
        # Check if it's a struct type we know about
        if member.is_struct or _is_known_struct(type_name, registry):
            # Find the struct definition
            struct_def = _find_struct_def(type_name, registry)
            if struct_def:
                emitted.add(type_name)
                w.line()
                w.line(f"typedef struct")
                w.block_open()
                for sm in struct_def.members:
                    dim_str = ''.join(f'[{d}]' for d in sm.dimensions)
                    w.line(f"{sm.type_name} {sm.name}{dim_str};")
                w.block_close(f" {type_name};")


def _is_known_struct(type_name, registry):
    """Check if a type is a known struct across any version."""
    for dt in registry.data_types.values():
        for dtv in dt.versions.values():
            for m in dtv.ctype.members:
                if m.type_name == type_name and m.is_struct:
                    return True
    # Check the parsed containers
    for iv in registry.interface_versions:
        if type_name in iv.container.types:
            ct = iv.container.types[type_name]
            if ct.is_struct:
                return True
    return False


def _find_struct_def(type_name, registry):
    """Find the struct definition for a type name."""
    for iv in registry.interface_versions:
        if type_name in iv.container.types:
            ct = iv.container.types[type_name]
            if ct.is_struct:
                return ct
    return None


def _generate_converter(dt, config, output_dir, warning_module=None):
    """Generate Converter_<TypeName>.h and .cpp."""
    sentinel = config['project'].get('generic_version_sentinel', 9999)
    conv = Converter(dt, config, warning_module=warning_module)

    # Generate header
    _generate_converter_header(dt, config, output_dir, conv)

    # Generate implementation
    _generate_converter_impl(dt, config, output_dir, conv)


def _generate_converter_header(dt, config, output_dir, conv):
    """Generate Converter_<TypeName>.h"""
    w = CodeWriter()
    w.line("#pragma once")
    w.line()
    w.line('#include "adapter_base.h"')
    w.line('#include "version_info.h"')
    w.line(f'#include "data_types/{dt.name}.h"')
    w.line()

    w.block_open(f"class Converter_{dt.name} : public AdapterConverterBase")
    w.line("public:")
    w.indent()
    w.line(f'static const char* GetConverterTypeName() {{ return "{dt.name}"; }}')
    w.line(f"static AdapterConverterBase* Create() {{ return new Converter_{dt.name}(); }}")
    w.line()
    w.line(f'const char* GetTypeName() const override {{ return "{dt.name}"; }}')
    w.line()
    w.line("long ConvertData(")
    w.indent()
    w.line("uint32_t src_type_tag, unsigned long src_size,")
    w.line("const IVersionInfo& src_version,")
    w.line("uint32_t dst_type_tag, unsigned long dst_size,")
    w.line("const IVersionInfo* dst_version,")
    w.line("void* dst_data,")
    w.line("void** out_data, unsigned long& out_size) override;")
    w.dedent()
    w.line()
    w.line("long GetDefaultValue(")
    w.indent()
    w.line("uint32_t type_tag, unsigned long size,")
    w.line("const IVersionInfo& version,")
    w.line("void** default_data, unsigned long& default_size) override;")
    w.dedent()
    w.line()
    w.line("bool AreVersionsCompatible(")
    w.indent()
    w.line("uint32_t src_type_tag, unsigned long src_size,")
    w.line("const IVersionInfo& src_version,")
    w.line("uint32_t dst_type_tag, unsigned long dst_size,")
    w.line("const IVersionInfo& dst_version) override;")
    w.dedent()
    w.dedent()
    w.line()
    w.line("private:")
    w.indent()

    # Forward converter declarations
    for ver_num in sorted(dt.versions.keys()):
        dtv = dt.versions[ver_num]
        if conv.are_structurally_identical(dtv, dt.generic):
            continue
        gen_ns = dt.generic.namespace
        src_ns = dtv.namespace
        w.line(f"void convert_V{ver_num}_to_Generic(")
        w.indent()
        w.line(f"{gen_ns}::{dt.name}& dest,")
        w.line(f"const {src_ns}::{dt.name}& source);")
        w.dedent()

    # Reverse converter declarations
    if dt.generate_reverse:
        for ver_num in sorted(dt.versions.keys()):
            dtv = dt.versions[ver_num]
            if conv.are_structurally_identical(dtv, dt.generic):
                continue
            gen_ns = dt.generic.namespace
            dst_ns = dtv.namespace
            w.line(f"void convert_Generic_to_V{ver_num}(")
            w.indent()
            w.line(f"{dst_ns}::{dt.name}& dest,")
            w.line(f"const {gen_ns}::{dt.name}& source);")
            w.dedent()

    w.dedent()
    w.block_close(";")

    filepath = os.path.join(output_dir, "converters", "generated", f"Converter_{dt.name}.h")
    w.write_to(filepath)


def _generate_converter_impl(dt, config, output_dir, conv):
    """Generate Converter_<TypeName>.cpp"""
    w = CodeWriter()
    w.line(f'#include "Converter_{dt.name}.h"')
    w.line("#include <cstring>")
    w.line()

    sentinel = config['project'].get('generic_version_sentinel', 9999)

    # ConvertData implementation
    w.line(f"long Converter_{dt.name}::ConvertData(")
    w.indent()
    w.line("uint32_t src_type_tag, unsigned long src_size,")
    w.line("const IVersionInfo& src_version,")
    w.line("uint32_t dst_type_tag, unsigned long dst_size,")
    w.line("const IVersionInfo* dst_version,")
    w.line("void* dst_data,")
    w.line("void** out_data, unsigned long& out_size)")
    w.dedent()
    w.block_open()
    w.line("uint32_t src_ver = src_version.GetVersion();")
    w.line(f"{dt.generic.namespace}::{dt.name} generic;")
    w.line()

    w.line("// Forward: source version -> generic")
    w.line("switch (src_ver)")
    w.block_open()
    for ver_num in sorted(dt.versions.keys()):
        dtv = dt.versions[ver_num]
        if conv.are_structurally_identical(dtv, dt.generic):
            w.line(f"case {ver_num}:")
            w.indent()
            w.line(f"memcpy(&generic, dst_data, sizeof(generic));")
            w.line("break;")
            w.dedent()
        else:
            w.line(f"case {ver_num}:")
            w.indent()
            w.line(f"convert_V{ver_num}_to_Generic(generic, *reinterpret_cast<const {dtv.namespace}::{dt.name}*>(dst_data));")
            w.line("break;")
            w.dedent()
    w.line("default:")
    w.indent()
    w.line("return -1;")
    w.dedent()
    w.block_close()
    w.line()

    w.line("// Output generic")
    w.line(f"out_size = sizeof({dt.generic.namespace}::{dt.name});")
    w.line(f"*out_data = new {dt.generic.namespace}::{dt.name}(generic);")
    w.line("return 0;")
    w.block_close()
    w.line()

    # GetDefaultValue
    w.line(f"long Converter_{dt.name}::GetDefaultValue(")
    w.indent()
    w.line("uint32_t type_tag, unsigned long size,")
    w.line("const IVersionInfo& version,")
    w.line("void** default_data, unsigned long& default_size)")
    w.dedent()
    w.block_open()
    w.line(f"{dt.generic.namespace}::{dt.name} def;")
    w.line("memset(&def, 0, sizeof(def));")
    w.line(f"default_size = sizeof({dt.generic.namespace}::{dt.name});")
    w.line(f"*default_data = new {dt.generic.namespace}::{dt.name}(def);")
    w.line("return 0;")
    w.block_close()
    w.line()

    # AreVersionsCompatible
    w.line(f"bool Converter_{dt.name}::AreVersionsCompatible(")
    w.indent()
    w.line("uint32_t src_type_tag, unsigned long src_size,")
    w.line("const IVersionInfo& src_version,")
    w.line("uint32_t dst_type_tag, unsigned long dst_size,")
    w.line("const IVersionInfo& dst_version)")
    w.dedent()
    w.block_open()
    w.line("return src_version.GetVersion() == dst_version.GetVersion();")
    w.block_close()
    w.line()

    # Forward converter implementations
    for ver_num in sorted(dt.versions.keys()):
        dtv = dt.versions[ver_num]
        if conv.are_structurally_identical(dtv, dt.generic):
            continue
        gen_ns = dt.generic.namespace
        src_ns = dtv.namespace
        w.line(f"void Converter_{dt.name}::convert_V{ver_num}_to_Generic(")
        w.indent()
        w.line(f"{gen_ns}::{dt.name}& dest,")
        w.line(f"const {src_ns}::{dt.name}& source)")
        w.dedent()
        w.block_open()
        conv.generate_forward_body(dtv, w)
        w.block_close()
        w.line()

    # Reverse converter implementations
    if dt.generate_reverse:
        for ver_num in sorted(dt.versions.keys()):
            dtv = dt.versions[ver_num]
            if conv.are_structurally_identical(dtv, dt.generic):
                continue
            gen_ns = dt.generic.namespace
            dst_ns = dtv.namespace
            w.line(f"void Converter_{dt.name}::convert_Generic_to_V{ver_num}(")
            w.indent()
            w.line(f"{dst_ns}::{dt.name}& dest,")
            w.line(f"const {gen_ns}::{dt.name}& source)")
            w.dedent()
            w.block_open()
            conv.generate_reverse_body(dtv, w)
            w.block_close()
            w.line()

    filepath = os.path.join(output_dir, "converters", "generated", f"Converter_{dt.name}.cpp")
    w.write_to(filepath)


def _generate_factory(data_types, output_dir):
    """Generate converters.cpp factory registration."""
    w = CodeWriter()
    w.line("#include <vector>")
    w.line("#include <string>")
    w.line("#include <functional>")
    for name in sorted(data_types.keys()):
        w.line(f'#include "Converter_{name}.h"')
    w.line()

    w.block_open("struct ConverterRegistration")
    w.line("std::string type_name;")
    w.line("std::function<AdapterConverterBase*()> factory;")
    w.block_close(";")
    w.line()

    w.block_open("std::vector<ConverterRegistration> GetGeneratedAdapters()")
    w.line("return {")
    w.indent()
    names = sorted(data_types.keys())
    for i, name in enumerate(names):
        comma = "," if i < len(names) - 1 else ""
        w.line(f"{{ Converter_{name}::GetConverterTypeName(),")
        w.line(f"  Converter_{name}::Create }}{comma}")
    w.dedent()
    w.line("};")
    w.block_close()

    filepath = os.path.join(output_dir, "converters", "generated", "converters.cpp")
    w.write_to(filepath)


def _generate_field_provenance(registry, output_dir):
    """Generate field_provenance.json."""
    from ductape.conv.field_provenance import generate_provenance
    provenance = generate_provenance(registry)
    filepath = os.path.join(output_dir, "field_provenance.json")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(provenance, f, indent=2)


def _generate_version_overview(registry, output_dir):
    """Generate version_overview.json listing each type's active versions (FR-11)."""
    overview = {}
    for type_name, dt in sorted(registry.data_types.items()):
        overview[type_name] = {
            'versions': sorted(dt.versions.keys()),
            'latest_version': max(dt.versions.keys()) if dt.versions else None,
            'version_count': len(dt.versions),
        }
    filepath = os.path.join(output_dir, "version_overview.json")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(overview, f, indent=2)


def _copy_platform_types(config, output_dir):
    """Copy platform_types.h to data_types output."""
    base_dir = config['_config_dir']
    for inc_dir in config.get('additional_includes', []):
        src_path = os.path.join(base_dir, inc_dir, 'platform_types.h')
        if os.path.isfile(src_path):
            dst_path = os.path.join(output_dir, 'data_types', 'platform_types.h')
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            with open(src_path) as f:
                content = f.read()
            with open(dst_path, 'w') as f:
                f.write(content)
            break


def run_verify(config_path, expected_dir, use_color=True):
    """Verify generated output against expected golden files."""
    import tempfile
    import filecmp

    with tempfile.TemporaryDirectory() as tmpdir:
        run_generate(config_path, tmpdir, use_color=use_color)

        # Compare all files
        differences = []
        for dirpath, dirnames, filenames in os.walk(expected_dir):
            for fname in filenames:
                expected_file = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(expected_file, expected_dir)
                generated_file = os.path.join(tmpdir, rel_path)

                if not os.path.isfile(generated_file):
                    differences.append(f"Missing: {rel_path}")
                elif not filecmp.cmp(expected_file, generated_file, shallow=False):
                    differences.append(f"Differs: {rel_path}")

        if differences:
            print("Verification FAILED:")
            for d in differences:
                print(f"  {d}")
            raise SystemExit(1)
        else:
            print("Verification PASSED: all files match.")
