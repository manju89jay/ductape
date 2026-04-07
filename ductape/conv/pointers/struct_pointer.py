"""Navigates into versioned struct members."""

from ductape.exceptions import AmbiguousMemberError


class StructPointer:
    """Wraps a CType + namespace for navigating struct members."""

    def __init__(self, ctype, namespace, container=None, parent=None):
        self.ctype = ctype
        self.namespace = namespace
        self.container = container
        self._parent = parent
        self._used = False

    @property
    def is_struct(self):
        return self.ctype.is_struct

    @property
    def is_array(self):
        return self.ctype.is_array

    @property
    def is_basic_type(self):
        return self.ctype.is_basic_type

    @property
    def pass_able(self):
        return True

    @property
    def parent_source(self):
        return self._parent

    @property
    def array_dimensions(self):
        return self.ctype.dimensions

    def enter_struct(self, field_name, type_hint=None):
        """Navigate into a named sub-field using 3-step fuzzy lookup."""
        members = self.ctype.members if self.ctype.members else []

        # Step 1: exact match
        for m in members:
            if m.name == field_name:
                child_ctype = self._resolve_member_type(m)
                return StructPointer(child_ctype, self.namespace,
                                     self.container, parent=self)

        # Step 2: name + "_" + type_hint match
        if type_hint:
            candidates = []
            pattern = f"{field_name}_{type_hint}"
            for m in members:
                if m.name == pattern:
                    candidates.append(m)
            if len(candidates) == 1:
                child_ctype = self._resolve_member_type(candidates[0])
                return StructPointer(child_ctype, self.namespace,
                                     self.container, parent=self)
            elif len(candidates) > 1:
                names = [c.name for c in candidates]
                raise AmbiguousMemberError(
                    f"Ambiguous match for '{field_name}' with hint '{type_hint}': {names}")

        # Step 3: strip type suffix and retry
        candidates = []
        for m in members:
            # Strip common suffixes
            stripped = m.name
            for suffix in ('_t', '_T', '_type'):
                if stripped.endswith(suffix):
                    stripped = stripped[:-len(suffix)]
            if stripped == field_name:
                candidates.append(m)

        if len(candidates) == 1:
            child_ctype = self._resolve_member_type(candidates[0])
            return StructPointer(child_ctype, self.namespace,
                                 self.container, parent=self)
        elif len(candidates) > 1:
            names = [c.name for c in candidates]
            raise AmbiguousMemberError(
                f"Ambiguous match for '{field_name}': {names}")

        return None

    def enter_array(self, dest=None):
        """Navigate into array element."""
        if not self.ctype.is_array:
            return None
        from ductape.conv.typecontainer import CType
        elem_type = CType(
            name=self.ctype.name,
            is_basic_type=self.ctype.is_basic_type,
            is_struct=self.ctype.is_struct,
            members=self.ctype.members,
        )
        return StructPointer(elem_type, self.namespace, self.container, parent=self)

    def _resolve_member_type(self, member):
        """Create a CType for a member."""
        from ductape.conv.typecontainer import CType
        if self.container and member.type_name in self.container.types:
            ct = self.container.types[member.type_name]
            return CType(
                name=member.type_name,
                is_struct=ct.is_struct,
                is_enum=ct.is_enum,
                is_basic_type=ct.is_basic_type,
                is_array=member.is_array,
                dimensions=list(member.dimensions),
                members=ct.members,
            )
        return CType(
            name=member.type_name,
            is_basic_type=member.is_basic_type,
            is_struct=member.is_struct,
            is_array=member.is_array,
            dimensions=list(member.dimensions),
        )
