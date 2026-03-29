"""Generates field-level conversion function bodies."""

from ductape.conv.code_writer import CodeWriter


class Converter:
    """Generates C++ conversion function bodies between struct versions."""

    def __init__(self, data_type, config, warning_module=None):
        self.data_type = data_type
        self.config = config
        self.renames = data_type.renames  # old_name -> new_name
        self.reverse_renames = {v: k for k, v in self.renames.items()}
        self.defaults = data_type.defaults
        self.warning_module = warning_module

    def are_structurally_identical(self, src_dtv, dst_dtv):
        """Check if two versions are structurally identical (FR-08)."""
        src_members = src_dtv.ctype.members
        dst_members = dst_dtv.ctype.members
        if len(src_members) != len(dst_members):
            return False
        for sm, dm in zip(src_members, dst_members):
            if sm.name != dm.name:
                return False
            if sm.type_name != dm.type_name:
                return False
            if sm.dimensions != dm.dimensions:
                return False
        return True

    def generate_forward_body(self, src_dtv, writer):
        """Generate V_N -> Generic conversion body."""
        generic = self.data_type.generic
        if not generic:
            return

        writer.line(f"memset(&dest, 0, sizeof(dest));")

        for dst_member in generic.ctype.members:
            dst_name = dst_member.name
            # Find source field name (may be renamed)
            src_name = self._find_src_field(dst_name, src_dtv)

            if src_name is not None:
                self._generate_field_copy(writer, src_name, dst_name,
                                          dst_member, src_dtv, generic)
            else:
                # Field doesn't exist in source - apply default if available
                self._generate_default(writer, dst_name, dst_member, src_dtv=src_dtv)

    def generate_reverse_body(self, dst_dtv, writer):
        """Generate Generic -> V_N conversion body."""
        generic = self.data_type.generic
        if not generic:
            return

        writer.line(f"memset(&dest, 0, sizeof(dest));")

        for dst_member in dst_dtv.ctype.members:
            dst_name = dst_member.name
            # Find the generic field name (may have been renamed)
            generic_name = self.renames.get(dst_name, dst_name)

            # Check if this generic field exists
            generic_member = None
            for gm in generic.ctype.members:
                if gm.name == generic_name:
                    generic_member = gm
                    break

            if generic_member is not None:
                self._generate_field_copy(writer, generic_name, dst_name,
                                          dst_member, generic, dst_dtv)
            else:
                self._generate_default(writer, dst_name, dst_member, src_dtv=dst_dtv)

    def _find_src_field(self, dst_name, src_dtv):
        """Find the source field name for a destination field."""
        # Check if dst_name exists directly in source
        for m in src_dtv.ctype.members:
            if m.name == dst_name:
                return dst_name

        # Check reverse rename: if dst_name was renamed from something
        old_name = self.reverse_renames.get(dst_name)
        if old_name:
            for m in src_dtv.ctype.members:
                if m.name == old_name:
                    return old_name

        return None

    def _find_member(self, name, dtv):
        """Find a member by name in a data type version."""
        for m in dtv.ctype.members:
            if m.name == name:
                return m
        return None

    def _generate_field_copy(self, writer, src_name, dst_name, dst_member,
                             src_dtv, dst_dtv):
        """Generate field copy code."""
        src_member = self._find_member(src_name, src_dtv)
        if src_member is None:
            return

        if src_member.is_array and dst_member.is_array:
            # Array copy with min dimension
            src_dims = src_member.dimensions
            dst_dims = dst_member.dimensions
            if src_dims and dst_dims:
                min_dim = f"({src_dims[0]} < {dst_dims[0]} ? {src_dims[0]} : {dst_dims[0]})"
                if src_dims[0] == dst_dims[0]:
                    min_dim = str(src_dims[0])
                writer.line(f"for (int i = 0; i < {min_dim}; i++)")
                writer.block_open()
                writer.line(f"dest.{dst_name}[i] = source.{src_name}[i];")
                writer.block_close()
            else:
                writer.line(f"dest.{dst_name} = source.{src_name};")
        elif src_member.is_struct:
            # Struct copy via memcpy (types are in different namespaces)
            writer.line(f"memcpy(&dest.{dst_name}, &source.{src_name}, sizeof(dest.{dst_name}));")
        else:
            # Simple field copy
            writer.line(f"dest.{dst_name} = source.{src_name};")

    def _emit_missing_field_warning(self, field_name, src_dtv, has_default):
        """Emit a warning when a source field is missing during conversion (FR-13)."""
        if self.warning_module is None:
            return
        # Check if there's a configured severity for this field
        fw = self.data_type.field_warnings.get(field_name, {})
        severity = fw.get('severity', 0 if has_default else 1)
        note = fw.get('note', '')
        if has_default:
            msg = (f"Field '{field_name}' missing in {self.data_type.name} "
                   f"V{src_dtv.version}; default applied")
        else:
            msg = (f"Field '{field_name}' missing in {self.data_type.name} "
                   f"V{src_dtv.version}; zero-initialized")
        if note:
            msg += f" ({note})"
        self.warning_module.add(msg, severity=severity,
                                context=f"{self.data_type.name}/V{src_dtv.version}")

    def _generate_default(self, writer, field_name, member, src_dtv=None):
        """Generate default value assignment."""
        # Look up default from flat dotted keys
        default_val = self._find_default(field_name)
        if default_val is not None:
            if member.is_struct:
                writer.line(f"// Default for struct field {field_name} (zero-initialized by memset)")
            else:
                writer.line(f"dest.{field_name} = {default_val};")
            if src_dtv is not None:
                self._emit_missing_field_warning(field_name, src_dtv, has_default=True)
        else:
            writer.line(f"// Field '{field_name}' not in source, zero-initialized by memset")
            if src_dtv is not None:
                self._emit_missing_field_warning(field_name, src_dtv, has_default=False)

    def _find_default(self, field_name):
        """Find default value from config defaults dict."""
        # Direct match
        if field_name in self.defaults:
            return self.defaults[field_name]
        return None
