"""Python dataclass emitter (FR-25 extension).

Generates Python dataclass definitions and converter functions
for each versioned data type. Output is pure Python with no
compiled dependencies.
"""

import os
from ductape.emitters.emitter_base import CodeEmitter, register_emitter


@register_emitter
class PythonEmitter(CodeEmitter):
    """Python dataclass + converter function emitter."""

    emitter_id = "python"

    def emit_type_header(self, data_type, output_dir, registry=None):
        """Emit Python dataclass definitions for all versions + generic."""
        dt = data_type
        lines = [
            '"""Auto-generated type definitions for {name}."""'.format(name=dt.name),
            "",
            "from dataclasses import dataclass, field",
            "",
        ]

        for ver_num in sorted(dt.versions.keys()):
            dtv = dt.versions[ver_num]
            lines.extend(self._emit_dataclass(dt.name, f"V{ver_num}", dtv))
            lines.append("")

        if dt.generic:
            lines.extend(self._emit_dataclass(dt.name, "Generic", dt.generic))
            lines.append("")

        filepath = os.path.join(output_dir, "types", f"{dt.name}.py")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            f.write('\n'.join(lines))

    def emit_converter(self, data_type, config, output_dir, warning_module=None):
        """Emit Python converter functions."""
        dt = data_type
        renames = dt.renames
        reverse_renames = {v: k for k, v in renames.items()}
        defaults = dt.defaults

        lines = [
            '"""Auto-generated converters for {name}."""'.format(name=dt.name),
            "",
            "from types.{name} import *".format(name=dt.name),
            "",
        ]

        # Forward converters
        for ver_num in sorted(dt.versions.keys()):
            dtv = dt.versions[ver_num]
            if dt.generic and self._are_identical(dtv, dt.generic):
                continue
            lines.extend(self._emit_forward_converter(
                dt, dtv, ver_num, renames, reverse_renames, defaults
            ))
            lines.append("")

        # Reverse converters
        if dt.generate_reverse and dt.generic:
            for ver_num in sorted(dt.versions.keys()):
                dtv = dt.versions[ver_num]
                if self._are_identical(dtv, dt.generic):
                    continue
                lines.extend(self._emit_reverse_converter(
                    dt, dtv, ver_num, renames, defaults
                ))
                lines.append("")

        filepath = os.path.join(output_dir, "converters", f"converter_{dt.name}.py")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            f.write('\n'.join(lines))

    def emit_factory(self, data_types, output_dir):
        """Emit Python converter registry."""
        lines = [
            '"""Auto-generated converter registry."""',
            "",
        ]

        for name in sorted(data_types.keys()):
            lines.append(f"from converters.converter_{name} import *")
        lines.append("")

        lines.append("CONVERTERS = {")
        for name in sorted(data_types.keys()):
            dt = data_types[name]
            lines.append(f'    "{name}": {{')
            lines.append(f'        "forward": {{')
            for ver_num in sorted(dt.versions.keys()):
                lines.append(f'            {ver_num}: convert_{name}_V{ver_num}_to_Generic,')
            lines.append(f'        }},')
            if dt.generate_reverse:
                lines.append(f'        "reverse": {{')
                for ver_num in sorted(dt.versions.keys()):
                    lines.append(f'            {ver_num}: convert_{name}_Generic_to_V{ver_num},')
                lines.append(f'        }},')
            lines.append(f'    }},')
        lines.append("}")
        lines.append("")

        filepath = os.path.join(output_dir, "converters", "registry.py")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            f.write('\n'.join(lines))

    # ── Private helpers ────────────────────────────────────────────

    def _emit_dataclass(self, type_name, version_label, dtv):
        """Generate a @dataclass for one version."""
        class_name = f"{type_name}_{version_label}"
        lines = ["@dataclass", f"class {class_name}:"]
        if not dtv.ctype.members:
            lines.append("    pass")
            return lines
        for member in dtv.ctype.members:
            py_type = self._c_to_python_type(member)
            default = self._python_default(member)
            lines.append(f"    {member.name}: {py_type} = {default}")
        return lines

    def _emit_forward_converter(self, dt, src_dtv, ver_num, renames, reverse_renames, defaults):
        """Generate V_N -> Generic converter function."""
        generic = dt.generic
        func_name = f"convert_{dt.name}_V{ver_num}_to_Generic"
        src_class = f"{dt.name}_V{ver_num}"
        gen_class = f"{dt.name}_Generic"

        lines = [f"def {func_name}(source: {src_class}) -> {gen_class}:"]
        lines.append(f"    dest = {gen_class}()")

        for dst_member in generic.ctype.members:
            dst_name = dst_member.name
            src_name = self._find_src_field(dst_name, src_dtv, reverse_renames)
            if src_name is not None:
                lines.append(f"    dest.{dst_name} = source.{src_name}")
            else:
                default_val = defaults.get(dst_name)
                if default_val is not None:
                    lines.append(f"    dest.{dst_name} = {default_val}")

        lines.append("    return dest")
        return lines

    def _emit_reverse_converter(self, dt, dst_dtv, ver_num, renames, defaults):
        """Generate Generic -> V_N converter function."""
        generic = dt.generic
        func_name = f"convert_{dt.name}_Generic_to_V{ver_num}"
        dst_class = f"{dt.name}_V{ver_num}"
        gen_class = f"{dt.name}_Generic"

        lines = [f"def {func_name}(source: {gen_class}) -> {dst_class}:"]
        lines.append(f"    dest = {dst_class}()")

        for dst_member in dst_dtv.ctype.members:
            dst_name = dst_member.name
            generic_name = renames.get(dst_name, dst_name)
            has_generic = any(gm.name == generic_name for gm in generic.ctype.members)
            if has_generic:
                lines.append(f"    dest.{dst_name} = source.{generic_name}")

        lines.append("    return dest")
        return lines

    def _find_src_field(self, dst_name, src_dtv, reverse_renames):
        for m in src_dtv.ctype.members:
            if m.name == dst_name:
                return dst_name
        old_name = reverse_renames.get(dst_name)
        if old_name:
            for m in src_dtv.ctype.members:
                if m.name == old_name:
                    return old_name
        return None

    def _are_identical(self, a, b):
        if len(a.ctype.members) != len(b.ctype.members):
            return False
        for ma, mb in zip(a.ctype.members, b.ctype.members):
            if ma.name != mb.name or ma.type_name != mb.type_name or ma.dimensions != mb.dimensions:
                return False
        return True

    def _c_to_python_type(self, member):
        int_types = {'uint8', 'sint8', 'uint16', 'sint16', 'uint32', 'sint32',
                     'uint64', 'sint64', 'uint8_t', 'int8_t', 'uint16_t',
                     'int16_t', 'uint32_t', 'int32_t', 'uint64_t', 'int64_t',
                     'int', 'short', 'long', 'boolean', 'bool', 'size_t'}
        float_types = {'float32', 'float64', 'float', 'double'}

        base = member.type_name
        if member.is_array:
            if base in int_types:
                return "list"
            elif base in float_types:
                return "list"
            return "list"
        if base in int_types:
            return "int"
        if base in float_types:
            return "float"
        if member.is_struct:
            return base
        return "int"

    def _python_default(self, member):
        if member.is_array:
            size = member.dimensions[0] if member.dimensions else 0
            return f"field(default_factory=lambda: [0] * {size})"
        if member.type_name in ('float32', 'float64', 'float', 'double'):
            return "0.0"
        return "0"
