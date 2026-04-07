"""Cross-version field audit + provenance report."""
from __future__ import annotations

from typing import Any

from ductape.conv.data_type_version import DataTypeVersion
from ductape.conv.typecontainer import CTypeMember


def generate_provenance(registry: Any) -> dict[str, dict[str, dict[str, Any]]]:
    """Generate field provenance data for all types."""
    provenance = {}

    for type_name, dt in registry.data_types.items():
        if dt.generic is None:
            continue

        type_prov = {}
        reverse_renames = {v: k for k, v in dt.renames.items()}

        for member in dt.generic.ctype.members:
            field_name = member.name
            field_info = {
                "generic_type": member.type_name,
                "versions": {},
                "type_compatible": True,
                "warnings": [],
            }

            field_types = set()
            default_versions = []

            for ver_num in sorted(dt.versions.keys()):
                dtv = dt.versions[ver_num]
                src_name = _find_field_in_version(field_name, dtv, dt.renames)

                if src_name is not None:
                    src_member = _get_member(src_name, dtv)
                    if src_member:
                        ver_entry = {
                            "type": src_member.type_name,
                            "field_name": src_name,
                        }
                        if src_name != field_name:
                            ver_entry["rename_from"] = src_name
                        field_info["versions"][str(ver_num)] = ver_entry
                        field_types.add(src_member.type_name)
                    else:
                        field_info["versions"][str(ver_num)] = None
                        default_versions.append(ver_num)
                else:
                    field_info["versions"][str(ver_num)] = None
                    default_versions.append(ver_num)

            if len(field_types) > 1:
                field_info["type_compatible"] = False

            if default_versions:
                field_info["default_applied_for"] = default_versions

            # Add field warnings from config
            if field_name in dt.field_warnings:
                fw = dt.field_warnings[field_name]
                field_info["warnings"].append({
                    "severity": fw.get("severity", 0),
                    "note": fw.get("note", ""),
                })

            type_prov[field_name] = field_info

        provenance[type_name] = type_prov

    return provenance


def _find_field_in_version(generic_name: str, dtv: DataTypeVersion, renames: dict[str, str]) -> str | None:
    """Find the source field name in a version."""
    reverse_renames = {v: k for k, v in renames.items()}

    # Direct match
    for m in dtv.ctype.members:
        if m.name == generic_name:
            return generic_name

    # Check reverse rename
    old_name = reverse_renames.get(generic_name)
    if old_name:
        for m in dtv.ctype.members:
            if m.name == old_name:
                return old_name

    return None


def _get_member(name: str, dtv: DataTypeVersion) -> CTypeMember | None:
    """Get a member by name from a data type version."""
    for m in dtv.ctype.members:
        if m.name == name:
            return m
    return None
