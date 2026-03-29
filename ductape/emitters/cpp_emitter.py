"""C++ code emitter (FR-25).

Wraps the existing C++ generation logic from codegen.py as a pluggable
CodeEmitter backend. Produces Converter_<Type>.h/.cpp and converters.cpp.
"""

import os
from ductape.emitters.emitter_base import CodeEmitter, register_emitter
from ductape.conv.code_writer import CodeWriter
from ductape.conv.converter import Converter


@register_emitter
class CppEmitter(CodeEmitter):
    """C++ class emitter producing AdapterConverterBase subclasses."""

    emitter_id = "cpp"

    def emit_type_header(self, data_type, output_dir, registry=None):
        """Emit data_types/<TypeName>.h with all version namespaces."""
        dt = data_type
        sentinel = max(dt.versions.keys()) + 1 if dt.versions else 9999
        # Use the generic version number as sentinel
        if dt.generic:
            sentinel = dt.generic.version

        w = CodeWriter()
        w.line("#pragma once")
        w.line('#include "platform_types.h"')
        w.line()

        w.line(f"#ifdef {dt.version_macro}")
        w.line(f"static_assert({dt.version_macro} != {sentinel},")
        w.line(f'  "Version {sentinel} is reserved as the generic adapter hub version");')
        w.line(f"#endif")
        w.line()

        for ver_num in sorted(dt.versions.keys()):
            dtv = dt.versions[ver_num]
            self._emit_version_namespace(w, dt, dtv, ver_num, registry)

        if dt.generic:
            self._emit_version_namespace(w, dt, dt.generic, sentinel, registry)

        filepath = os.path.join(output_dir, "data_types", f"{dt.name}.h")
        w.write_to(filepath)

    def emit_converter(self, data_type, config, output_dir, warning_module=None):
        """Emit Converter_<TypeName>.h and .cpp."""
        dt = data_type
        conv = Converter(dt, config, warning_module=warning_module)
        self._emit_converter_header(dt, config, output_dir, conv)
        self._emit_converter_impl(dt, config, output_dir, conv)

    def emit_factory(self, data_types, output_dir):
        """Emit converters.cpp factory registration."""
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

    def emit_platform_types(self, config, output_dir):
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

    def emit_version_negotiation(self, data_types, output_dir):
        """Emit version_negotiation.h with runtime version query helpers."""
        w = CodeWriter()
        w.line("#pragma once")
        w.line("#include <cstdint>")
        w.line("#include <vector>")
        w.line("#include <algorithm>")
        w.line()
        w.block_open("namespace ductape")
        w.line()

        for name in sorted(data_types.keys()):
            dt = data_types[name]
            versions = sorted(dt.versions.keys())
            w.line(f"/* Version info for {name} */")
            w.line(f"inline std::vector<uint32_t> {name}_GetSupportedVersions()")
            w.block_open()
            v_list = ", ".join(str(v) for v in versions)
            w.line(f"return {{ {v_list} }};")
            w.block_close()
            w.line()
            w.line(f"inline uint32_t {name}_GetLatestVersion()")
            w.block_open()
            w.line(f"return {versions[-1] if versions else 0};")
            w.block_close()
            w.line()

        w.line("/* Find best common version between two version sets */")
        w.line("inline uint32_t NegotiateBestVersion(")
        w.indent()
        w.line("const std::vector<uint32_t>& local_versions,")
        w.line("const std::vector<uint32_t>& remote_versions)")
        w.dedent()
        w.block_open()
        w.line("uint32_t best = 0;")
        w.line("for (auto v : local_versions)")
        w.block_open()
        w.line("if (std::find(remote_versions.begin(), remote_versions.end(), v) != remote_versions.end())")
        w.indent()
        w.line("if (v > best) best = v;")
        w.dedent()
        w.block_close()
        w.line("return best;")
        w.block_close()
        w.line()

        w.block_close(" // namespace ductape")

        filepath = os.path.join(output_dir, "converters", "generated", "version_negotiation.h")
        w.write_to(filepath)

    # ── Private helpers ────────────────────────────────────────────

    def _emit_version_namespace(self, w, dt, dtv, version, registry):
        ns = dtv.namespace
        w.block_open(f"namespace {ns}")
        w.line(f"static const uint32_t VERSION = {version};")

        emitted_types = set()
        self._emit_dependent_types(w, dtv, dt.name, emitted_types, registry)

        w.line()
        w.line("typedef struct")
        w.block_open()
        for member in dtv.ctype.members:
            dim_str = ''.join(f'[{d}]' for d in member.dimensions)
            w.line(f"{member.type_name} {member.name}{dim_str};")
        w.block_close(f" {dt.name};")
        w.block_close(f" // namespace {ns}")
        w.line()

    def _emit_dependent_types(self, w, dtv, parent_name, emitted, registry):
        if registry is None:
            return
        for member in dtv.ctype.members:
            type_name = member.type_name
            if type_name == parent_name or type_name in emitted:
                continue
            if member.is_struct or self._is_known_struct(type_name, registry):
                struct_def = self._find_struct_def(type_name, registry)
                if struct_def:
                    emitted.add(type_name)
                    w.line()
                    w.line("typedef struct")
                    w.block_open()
                    for sm in struct_def.members:
                        dim_str = ''.join(f'[{d}]' for d in sm.dimensions)
                        w.line(f"{sm.type_name} {sm.name}{dim_str};")
                    w.block_close(f" {type_name};")

    def _is_known_struct(self, type_name, registry):
        for dt in registry.data_types.values():
            for dtv in dt.versions.values():
                for m in dtv.ctype.members:
                    if m.type_name == type_name and m.is_struct:
                        return True
        for iv in registry.interface_versions:
            if type_name in iv.container.types:
                if iv.container.types[type_name].is_struct:
                    return True
        return False

    def _find_struct_def(self, type_name, registry):
        for iv in registry.interface_versions:
            if type_name in iv.container.types:
                ct = iv.container.types[type_name]
                if ct.is_struct:
                    return ct
        return None

    def _emit_converter_header(self, dt, config, output_dir, conv):
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

    def _emit_converter_impl(self, dt, config, output_dir, conv):
        w = CodeWriter()
        w.line(f'#include "Converter_{dt.name}.h"')
        w.line("#include <cstring>")
        w.line()

        # ConvertData
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
