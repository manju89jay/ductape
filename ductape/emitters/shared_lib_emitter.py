"""Shared library emitter (FR-26).

Emits C source code with a stable C ABI that compiles into a .so/.dll.
Exports: GetConverterVersion(), ConvertData(), GetSupportedVersions().
Loadable at runtime via dlopen/LoadLibrary without process restart.
"""

import os
from ductape.emitters.emitter_base import CodeEmitter, register_emitter
from ductape.conv.code_writer import CodeWriter
from ductape.conv.converter import Converter


@register_emitter
class SharedLibEmitter(CodeEmitter):
    """Shared library (.so/.dll) emitter with stable C ABI."""

    emitter_id = "shared_lib"

    def emit_type_header(self, data_type, output_dir, registry=None):
        """Emit C-compatible type definitions header."""
        dt = data_type
        sentinel = dt.generic.version if dt.generic else 9999

        w = CodeWriter()
        w.line("#pragma once")
        w.line("#include <stdint.h>")
        w.line("#include <string.h>")
        w.line()

        w.line("/* Type definitions for all versions */")
        w.line()

        # Emit dependent struct types first (e.g. BatteryInfo_t)
        emitted_deps = set()
        all_dtvs = [dt.versions[v] for v in sorted(dt.versions.keys())]
        if dt.generic:
            all_dtvs.append(dt.generic)
        for dtv in all_dtvs:
            self._emit_dependent_structs(w, dtv, dt.name, emitted_deps, registry)

        for ver_num in sorted(dt.versions.keys()):
            dtv = dt.versions[ver_num]
            self._emit_c_struct(w, dt.name, dtv, f"v{ver_num}")

        if dt.generic:
            self._emit_c_struct(w, dt.name, dt.generic, "generic")

        filepath = os.path.join(output_dir, "shared_lib", f"{dt.name}_types.h")
        w.write_to(filepath)

    def emit_converter(self, data_type, config, output_dir, warning_module=None):
        """Emit C-ABI converter source file."""
        dt = data_type
        conv = Converter(dt, config, warning_module=warning_module)
        sentinel = dt.generic.version if dt.generic else 9999

        w = CodeWriter()
        w.line(f'#include "{dt.name}_types.h"')
        w.line()

        # Version query function
        w.line(f"/* Exported C ABI functions for {dt.name} */")
        w.line()
        w.line("#ifdef _WIN32")
        w.line("#define EXPORT __declspec(dllexport)")
        w.line("#else")
        w.line("#define EXPORT __attribute__((visibility(\"default\")))")
        w.line("#endif")
        w.line()

        # GetConverterVersion
        w.line(f"EXPORT uint32_t {dt.name}_GetConverterVersion(void)")
        w.block_open()
        w.line("return 1; /* Converter ABI version */")
        w.block_close()
        w.line()

        # GetSupportedVersions
        versions = sorted(dt.versions.keys())
        w.line(f"static const uint32_t {dt.name}_supported_versions[] = {{")
        w.indent()
        w.line(", ".join(str(v) for v in versions))
        w.dedent()
        w.line("};")
        w.line()
        w.line(f"EXPORT uint32_t {dt.name}_GetSupportedVersionCount(void)")
        w.block_open()
        w.line(f"return {len(versions)};")
        w.block_close()
        w.line()
        w.line(f"EXPORT const uint32_t* {dt.name}_GetSupportedVersions(void)")
        w.block_open()
        w.line(f"return {dt.name}_supported_versions;")
        w.block_close()
        w.line()

        # Forward conversion functions per version
        for ver_num in sorted(dt.versions.keys()):
            dtv = dt.versions[ver_num]
            if conv.are_structurally_identical(dtv, dt.generic):
                continue
            v_prefix = f"{dt.name}_v{ver_num}"
            g_prefix = f"{dt.name}_generic"
            w.line(f"static void convert_{v_prefix}_to_generic(")
            w.indent()
            w.line(f"struct {g_prefix}* dest,")
            w.line(f"const struct {v_prefix}* source)")
            w.dedent()
            w.block_open()
            w.line("memset(dest, 0, sizeof(*dest));")
            self._emit_field_copies(w, dtv, dt.generic, conv, dt)
            w.block_close()
            w.line()

        # Reverse conversion functions
        if dt.generate_reverse:
            for ver_num in sorted(dt.versions.keys()):
                dtv = dt.versions[ver_num]
                if conv.are_structurally_identical(dtv, dt.generic):
                    continue
                v_prefix = f"{dt.name}_v{ver_num}"
                g_prefix = f"{dt.name}_generic"
                w.line(f"static void convert_generic_to_{v_prefix}(")
                w.indent()
                w.line(f"struct {v_prefix}* dest,")
                w.line(f"const struct {g_prefix}* source)")
                w.dedent()
                w.block_open()
                w.line("memset(dest, 0, sizeof(*dest));")
                self._emit_field_copies(w, dt.generic, dtv, conv, dt)
                w.block_close()
                w.line()

        # ConvertData dispatcher
        w.line(f"EXPORT int {dt.name}_ConvertData(")
        w.indent()
        w.line("uint32_t src_version,")
        w.line("const void* src_data,")
        w.line("void* dst_data,")
        w.line("uint32_t dst_size)")
        w.dedent()
        w.block_open()
        w.line(f"struct {dt.name}_generic* generic = (struct {dt.name}_generic*)dst_data;")
        w.line("switch (src_version)")
        w.block_open()
        for ver_num in sorted(dt.versions.keys()):
            dtv = dt.versions[ver_num]
            v_prefix = f"{dt.name}_v{ver_num}"
            w.line(f"case {ver_num}:")
            w.indent()
            if conv.are_structurally_identical(dtv, dt.generic):
                w.line(f"memcpy(generic, src_data, sizeof(*generic));")
            else:
                w.line(f"convert_{v_prefix}_to_generic(generic, (const struct {v_prefix}*)src_data);")
            w.line("return 0;")
            w.dedent()
        w.line("default:")
        w.indent()
        w.line("return -1;")
        w.dedent()
        w.block_close()
        w.block_close()
        w.line()

        filepath = os.path.join(output_dir, "shared_lib", f"{dt.name}_converter.c")
        w.write_to(filepath)

    def emit_factory(self, data_types, output_dir):
        """Emit shared library factory registration header."""
        w = CodeWriter()
        w.line("#pragma once")
        w.line("#include <stdint.h>")
        w.line()
        w.line("#ifdef _WIN32")
        w.line("#define EXPORT __declspec(dllexport)")
        w.line("#else")
        w.line("#define EXPORT __attribute__((visibility(\"default\")))")
        w.line("#endif")
        w.line()

        for name in sorted(data_types.keys()):
            w.line(f"/* {name} exports */")
            w.line(f"EXPORT uint32_t {name}_GetConverterVersion(void);")
            w.line(f"EXPORT uint32_t {name}_GetSupportedVersionCount(void);")
            w.line(f"EXPORT const uint32_t* {name}_GetSupportedVersions(void);")
            w.line(f"EXPORT int {name}_ConvertData(")
            w.indent()
            w.line("uint32_t src_version, const void* src_data,")
            w.line("void* dst_data, uint32_t dst_size);")
            w.dedent()
            w.line()

        filepath = os.path.join(output_dir, "shared_lib", "adapter_exports.h")
        w.write_to(filepath)

    # ── Private helpers ────────────────────────────────────────────

    def _emit_dependent_structs(self, w, dtv, parent_name, emitted, registry):
        """Emit C structs for dependent types (e.g. BatteryInfo_t)."""
        if registry is None:
            return
        for member in dtv.ctype.members:
            tname = member.type_name
            if tname == parent_name or tname in emitted:
                continue
            if not member.is_struct:
                continue
            # Find struct definition in registry
            struct_def = None
            for iv in registry.interface_versions:
                if tname in iv.container.types:
                    ct = iv.container.types[tname]
                    if ct.is_struct:
                        struct_def = ct
                        break
            if struct_def:
                emitted.add(tname)
                w.line(f"struct {tname}")
                w.block_open()
                for sm in struct_def.members:
                    dim_str = ''.join(f'[{d}]' for d in sm.dimensions)
                    c_type = self._cpp_to_c_type(sm.type_name)
                    w.line(f"{c_type} {sm.name}{dim_str};")
                w.block_close(";")
                w.line()

    def _emit_c_struct(self, w, type_name, dtv, version_label):
        """Emit a plain C struct for a version."""
        struct_name = f"{type_name}_{version_label}"
        w.line(f"struct {struct_name}")
        w.block_open()
        for member in dtv.ctype.members:
            dim_str = ''.join(f'[{d}]' for d in member.dimensions)
            if member.is_struct:
                w.line(f"struct {member.type_name} {member.name}{dim_str};")
            else:
                c_type = self._cpp_to_c_type(member.type_name)
                w.line(f"{c_type} {member.name}{dim_str};")
        w.block_close(";")
        w.line()

    def _cpp_to_c_type(self, type_name):
        """Map platform types to C stdint types."""
        mapping = {
            'uint8': 'uint8_t', 'sint8': 'int8_t',
            'uint16': 'uint16_t', 'sint16': 'int16_t',
            'uint32': 'uint32_t', 'sint32': 'int32_t',
            'uint64': 'uint64_t', 'sint64': 'int64_t',
            'float32': 'float', 'float64': 'double',
            'boolean': 'uint8_t',
        }
        return mapping.get(type_name, type_name)

    def _emit_field_copies(self, w, src_dtv, dst_dtv, conv, dt):
        """Emit field-by-field copy in C style."""
        renames = dt.renames
        reverse_renames = {v: k for k, v in renames.items()}
        defaults = dt.defaults

        for dst_member in dst_dtv.ctype.members:
            dst_name = dst_member.name
            # Find source field name
            src_name = self._find_src_field(dst_name, src_dtv, renames, reverse_renames)

            if src_name is not None:
                src_member = None
                for m in src_dtv.ctype.members:
                    if m.name == src_name:
                        src_member = m
                        break
                if src_member and src_member.is_array and dst_member.is_array:
                    src_dim = src_member.dimensions[0] if src_member.dimensions else 0
                    dst_dim = dst_member.dimensions[0] if dst_member.dimensions else 0
                    if src_dim == dst_dim:
                        min_dim = str(src_dim)
                    else:
                        min_dim = f"({src_dim} < {dst_dim} ? {src_dim} : {dst_dim})"
                    w.line(f"for (int i = 0; i < {min_dim}; i++)")
                    w.indent()
                    w.line(f"dest->{dst_name}[i] = source->{src_name}[i];")
                    w.dedent()
                elif src_member and src_member.is_struct:
                    w.line(f"memcpy(&dest->{dst_name}, &source->{src_name}, sizeof(dest->{dst_name}));")
                else:
                    w.line(f"dest->{dst_name} = source->{src_name};")
            else:
                default_val = defaults.get(dst_name)
                if default_val is not None and not dst_member.is_struct:
                    w.line(f"dest->{dst_name} = {default_val};")
                else:
                    w.line(f"/* {dst_name}: not in source, zero from memset */")

    def _find_src_field(self, dst_name, src_dtv, renames, reverse_renames):
        for m in src_dtv.ctype.members:
            if m.name == dst_name:
                return dst_name
        old_name = reverse_renames.get(dst_name)
        if old_name:
            for m in src_dtv.ctype.members:
                if m.name == old_name:
                    return old_name
        return None
