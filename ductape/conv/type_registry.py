"""Registry + orchestrator: drives generation steps."""

from ductape.conv.data_type import DataType
from ductape.conv.interface_version import InterfaceVersion


class VersionConflictError(Exception):
    """Raised when the same version number has structurally different layouts (FR-14)."""
    pass


class TypeRegistry:
    """Collects all types from all versions and builds generics."""

    def __init__(self, config):
        self.config = config
        self.data_types = {}  # type_name -> DataType
        self.interface_versions = []  # list of InterfaceVersion
        self.semantic_warnings = []

    def load_all(self):
        """Parse all header sources and register types."""
        base_dir = self.config['_config_dir']
        version_macros = {
            name: cfg['version_macro']
            for name, cfg in self.config['types'].items()
        }
        additional_includes = self.config.get('additional_includes', [])

        # Initialize DataType objects
        for type_name, type_cfg in self.config['types'].items():
            dt = DataType(
                name=type_name,
                version_macro=type_cfg['version_macro'],
                defaults=type_cfg.get('defaults', {}),
                renames=type_cfg.get('renames', {}),
                field_warnings=type_cfg.get('field_warnings', {}),
                enum_mappings=type_cfg.get('enum_mappings', {}),
                generate_reverse=type_cfg.get('generate_reverse', False),
            )
            self.data_types[type_name] = dt

        # Parse each header source
        for source in self.config['header_sources']:
            iv = InterfaceVersion(
                base_dir=base_dir,
                path=source['path'],
                version_tag=source['version_tag'],
                additional_includes=additional_includes,
            )
            iv.parse(version_macros)
            self.interface_versions.append(iv)

            # Register types found, with version conflict detection (FR-14)
            for type_name, dt in self.data_types.items():
                if type_name in iv.container.types and type_name in iv.version_numbers:
                    ver_num = iv.version_numbers[type_name]
                    new_ctype = iv.container.types[type_name]
                    if ver_num in dt.versions:
                        self._check_version_conflict(
                            type_name, ver_num,
                            dt.versions[ver_num].ctype, new_ctype,
                        )
                    else:
                        dt.add_version(ver_num, new_ctype)

        # Build generics
        sentinel = self.config['project'].get('generic_version_sentinel', 9999)
        for dt in self.data_types.values():
            dt.build_generic(sentinel)

        # Run semantic checks
        self._check_field_compatibility()

    def _check_version_conflict(self, type_name, version, existing_ctype, new_ctype):
        """Detect version conflicts: same version number, different layout (FR-14)."""
        if len(existing_ctype.members) != len(new_ctype.members):
            raise VersionConflictError(
                f"Version conflict for '{type_name}' version {version}: "
                f"different number of members "
                f"({len(existing_ctype.members)} vs {len(new_ctype.members)})"
            )
        for old_m, new_m in zip(existing_ctype.members, new_ctype.members):
            if (old_m.name != new_m.name
                    or old_m.type_name != new_m.type_name
                    or old_m.dimensions != new_m.dimensions):
                raise VersionConflictError(
                    f"Version conflict for '{type_name}' version {version}: "
                    f"structural mismatch at field '{old_m.name}' vs '{new_m.name}'"
                )

    def _check_field_compatibility(self):
        """Check field type compatibility across versions (FR-20)."""
        for dt in self.data_types.values():
            if dt.generic is None:
                continue
            for member in dt.generic.ctype.members:
                field_types = {}
                for ver_num, dtv in dt.versions.items():
                    # Find this field in the version (with rename awareness)
                    src_name = self._find_source_field_name(dt, member.name, dtv)
                    if src_name is None:
                        continue
                    for src_member in dtv.ctype.members:
                        if src_member.name == src_name:
                            field_types[ver_num] = src_member.type_name
                            break

                # Check consistency
                unique_types = set(field_types.values())
                if len(unique_types) > 1:
                    self.semantic_warnings.append({
                        'type': dt.name,
                        'field': member.name,
                        'severity': 2,
                        'message': f"Field '{member.name}' has different types across versions: {field_types}",
                    })

    def _find_source_field_name(self, dt, generic_name, dtv):
        """Find the source field name for a generic field, considering renames."""
        # Check if there's a reverse rename (new_name -> old_name)
        reverse_renames = {v: k for k, v in dt.renames.items()}
        old_name = reverse_renames.get(generic_name, generic_name)

        # Check if version has the canonical name
        for m in dtv.ctype.members:
            if m.name == generic_name:
                return generic_name
            if m.name == old_name:
                return old_name
        return None
