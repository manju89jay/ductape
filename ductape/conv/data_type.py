"""One logical type across all its versions."""
from __future__ import annotations

from dataclasses import dataclass, field

from ductape.conv.data_type_version import DataTypeVersion
from ductape.conv.typecontainer import CType, CTypeMember


class GenericVersion:
    """Tag class for the generic hub version."""
    pass


@dataclass
class DataType:
    """A logical data type with all its versions and a generic superset."""
    name: str
    version_macro: str
    versions: dict[int, DataTypeVersion] = field(default_factory=dict)  # version_num -> DataTypeVersion
    defaults: dict[str, str] = field(default_factory=dict)
    renames: dict[str, str] = field(default_factory=dict)  # old_name -> new_name
    field_warnings: dict[str, dict[str, object]] = field(default_factory=dict)
    enum_mappings: dict[str, dict[str, str]] = field(default_factory=dict)  # field_name -> {old_val: new_val}
    generate_reverse: bool = False
    generic: DataTypeVersion | None = None

    def add_version(self, version_num: int, ctype: CType) -> None:
        dtv = DataTypeVersion(
            type_name=self.name,
            version=version_num,
            ctype=ctype,
        )
        self.versions[version_num] = dtv

    def build_generic(self, sentinel: int = 9999) -> DataTypeVersion:
        """Build the generic (superset) version from all known versions."""
        all_members = {}  # name -> CTypeMember (keep last seen)
        member_order = []

        # Apply renames: old_name -> new_name
        reverse_renames = {v: k for k, v in self.renames.items()}

        for ver_num in sorted(self.versions.keys()):
            dtv = self.versions[ver_num]
            for member in dtv.ctype.members:
                # Check if this member name has a rename
                canonical_name = self.renames.get(member.name, member.name)
                if canonical_name not in all_members:
                    # Create member with canonical name
                    gen_member = CTypeMember(
                        name=canonical_name,
                        type_name=member.type_name,
                        is_array=member.is_array,
                        dimensions=list(member.dimensions),
                        is_struct=member.is_struct,
                        is_enum=member.is_enum,
                        is_basic_type=member.is_basic_type,
                        bitfield_width=member.bitfield_width,
                    )
                    all_members[canonical_name] = gen_member
                    member_order.append(canonical_name)
                else:
                    # Update dimensions to max
                    existing = all_members[canonical_name]
                    if member.dimensions:
                        for i, dim in enumerate(member.dimensions):
                            if i < len(existing.dimensions):
                                existing.dimensions[i] = max(existing.dimensions[i], dim)
                            else:
                                existing.dimensions.append(dim)

        generic_ctype = CType(
            name=self.name,
            is_struct=True,
            members=[all_members[n] for n in member_order],
        )
        self.generic = DataTypeVersion(
            type_name=self.name,
            version=sentinel,
            ctype=generic_ctype,
            namespace=f"{self.name}_V_Gen",
        )
        return self.generic
