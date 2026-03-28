"""Two-stage adaptation pipeline (FR-27).

Stage 1: Intra-format versioning — normalizes within a format family
         (e.g. Protobuf V1/V2/V3 -> Protobuf canonical).
Stage 2: Cross-format normalization — maps between format families
         (e.g. Protobuf canonical -> C struct canonical).

Both stages use the same hub-and-spoke engine. Field mapping, default
injection, rename handling, and provenance tracking are identical.
"""

import os
import json
from dataclasses import dataclass, field
from typing import Optional

from ductape.conv.typecontainer import TypeContainer, CType, CTypeMember
from ductape.conv.data_type import DataType
from ductape.conv.data_type_version import DataTypeVersion
from ductape.conv.converter import Converter
from ductape.conv.code_writer import CodeWriter
from ductape.warnings import WarningModule


@dataclass
class StageResult:
    """Result from a pipeline stage."""
    data_types: dict = field(default_factory=dict)  # name -> DataType
    containers: list = field(default_factory=list)   # list of TypeContainer


@dataclass
class FieldMapping:
    """A single field mapping from source to target."""
    source_field: str
    target_field: str


class TwoStagePipeline:
    """Orchestrates two-stage adaptation from heterogeneous sources."""

    def __init__(self, pipeline_config, warning_module=None):
        """Initialize pipeline from config.

        Args:
            pipeline_config: dict with 'sources' key containing stage definitions
            warning_module: optional WarningModule for diagnostics
        """
        self.config = pipeline_config
        self.warning_module = warning_module or WarningModule(use_color=False)
        self.stage1_results = {}  # source_name -> StageResult
        self.stage2_result = None

    def run_stage1(self, source_name, source_config, containers):
        """Run Stage 1: intra-format versioning for one source.

        Builds DataType objects from parsed containers, creates generic
        hub version, and produces converters within the format family.

        Args:
            source_name: identifier for this source
            source_config: dict with stage1 config (hub_version, types, etc.)
            containers: list of (version_tag, TypeContainer) tuples
        Returns:
            StageResult with fully resolved data types
        """
        stage1_cfg = source_config.get('stage1', {})
        types_cfg = stage1_cfg.get('types', {})
        sentinel = 9999

        result = StageResult()

        for type_name, type_cfg in types_cfg.items():
            dt = DataType(
                name=type_name,
                version_macro=type_cfg.get('version_field', f'{type_name}_VERSION'),
                defaults=type_cfg.get('defaults', {}),
                renames=type_cfg.get('renames', {}),
                field_warnings=type_cfg.get('field_warnings', {}),
                generate_reverse=type_cfg.get('generate_reverse', False),
            )

            # Register versions from containers
            for ver_idx, (version_tag, container) in enumerate(containers):
                ver_num = ver_idx + 1
                if type_name in container.types:
                    dt.add_version(ver_num, container.types[type_name])

            # Build generic
            dt.build_generic(sentinel)
            result.data_types[type_name] = dt

        result.containers = [c for _, c in containers]
        self.stage1_results[source_name] = result
        return result

    def run_stage2(self, stage2_config, stage1_results):
        """Run Stage 2: cross-format normalization.

        Maps fields from stage1 canonical types to target types using
        configured field mappings.

        Args:
            stage2_config: dict with type_mappings and field_mappings
            stage1_results: dict of source_name -> StageResult
        Returns:
            StageResult with cross-format mapped types
        """
        type_mappings = stage2_config.get('type_mappings', {})
        field_mappings = stage2_config.get('field_mappings', {})

        result = StageResult()

        for src_type, dst_type in type_mappings.items():
            # Find the source DataType from any stage1 result
            src_dt = None
            for src_name, sr in stage1_results.items():
                if src_type in sr.data_types:
                    src_dt = sr.data_types[src_type]
                    break

            if src_dt is None or src_dt.generic is None:
                if self.warning_module:
                    self.warning_module.add(
                        f"Stage 2: source type '{src_type}' not found in any stage 1 result",
                        severity=2, context="two_stage"
                    )
                continue

            # Build mapped type from generic
            mappings = field_mappings.get(src_type, {})
            mapped_members = []

            for member in src_dt.generic.ctype.members:
                target_field = mappings.get(member.name, member.name)
                mapped_members.append(CTypeMember(
                    name=target_field,
                    type_name=member.type_name,
                    is_array=member.is_array,
                    dimensions=list(member.dimensions),
                    is_struct=member.is_struct,
                    is_enum=member.is_enum,
                    is_basic_type=member.is_basic_type,
                ))

            mapped_ctype = CType(
                name=dst_type, is_struct=True, members=mapped_members,
            )
            mapped_dtv = DataTypeVersion(
                type_name=dst_type, version=9999, ctype=mapped_ctype,
                namespace=f"{dst_type}_V_Gen",
            )

            # Create a DataType for the mapped output
            dt = DataType(
                name=dst_type,
                version_macro=f"{dst_type}_VERSION",
            )
            # The mapped type has a single "version" which is the cross-format result
            dt.generic = mapped_dtv
            # Copy the source versions as the input versions
            for ver_num, src_dtv in src_dt.versions.items():
                dt.add_version(ver_num, src_dtv.ctype)

            result.data_types[dst_type] = dt

        self.stage2_result = result
        return result

    def run(self, parsed_sources):
        """Run the full two-stage pipeline.

        Args:
            parsed_sources: dict of source_name -> {
                'config': source config dict,
                'containers': list of (version_tag, TypeContainer),
            }
        Returns:
            dict with 'stage1' and 'stage2' results
        """
        sources_config = self.config.get('sources', {})

        # Stage 1: process each source independently
        for source_name, source_data in parsed_sources.items():
            source_cfg = sources_config.get(source_name, source_data.get('config', {}))
            self.run_stage1(
                source_name, source_cfg, source_data['containers']
            )

        # Stage 2: cross-format mapping
        stage2_config = self.config.get('stage2', {})
        if stage2_config:
            self.run_stage2(stage2_config, self.stage1_results)

        return {
            'stage1': self.stage1_results,
            'stage2': self.stage2_result,
        }

    def generate_provenance(self):
        """Generate provenance report for the two-stage pipeline.

        Returns:
            dict with stage1 and stage2 provenance info
        """
        report = {'stage1': {}, 'stage2': {}}

        for source_name, sr in self.stage1_results.items():
            report['stage1'][source_name] = {}
            for type_name, dt in sr.data_types.items():
                report['stage1'][source_name][type_name] = {
                    'versions': sorted(dt.versions.keys()),
                    'generic_fields': [m.name for m in dt.generic.ctype.members]
                    if dt.generic else [],
                }

        if self.stage2_result:
            for type_name, dt in self.stage2_result.data_types.items():
                report['stage2'][type_name] = {
                    'mapped_fields': [m.name for m in dt.generic.ctype.members]
                    if dt.generic else [],
                    'source_versions': sorted(dt.versions.keys()),
                }

        return report
