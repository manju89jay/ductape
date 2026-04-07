"""Generation driver - top-level orchestrator."""
from __future__ import annotations

import logging
import os
import tempfile
import filecmp

from ductape.config import load_config
from ductape.conv.type_registry import TypeRegistry
from ductape.warnings import WarningModule
from ductape import builtin_codegen

# Import frontends and emitters to trigger registration
import ductape.frontends.c_header  # noqa: F401
import ductape.frontends.protobuf  # noqa: F401
import ductape.frontends.json_schema  # noqa: F401
import ductape.emitters.cpp_emitter  # noqa: F401
import ductape.emitters.shared_lib_emitter  # noqa: F401
import ductape.emitters.python_emitter  # noqa: F401

logger = logging.getLogger(__name__)


def run_generate(config_path: str, output_dir: str, *,
                 use_color: bool = True, dry_run: bool = False) -> None:
    """Run the full generation pipeline."""
    logger.info("Loading config from %s", config_path)
    config = load_config(config_path)
    registry = TypeRegistry(config)
    registry.load_all()
    logger.info("Loaded %d type(s) from %d header source(s)",
                len(registry.data_types), len(registry.interface_versions))

    sentinel = config['project'].get('generic_version_sentinel', 9999)

    # Create warning module (FR-13)
    warn_cfg = config.get('warnings', {})
    warning_module = WarningModule(
        min_severity=warn_cfg.get('min_display_severity', 1),
        use_color=use_color and warn_cfg.get('color', True),
    )

    if dry_run:
        _print_dry_run(registry, config, output_dir)
        return

    os.makedirs(output_dir, exist_ok=True)

    # Select emitter based on config (FR-25), default to cpp
    emitter_id = config.get('emitter', 'cpp')
    emitter = _get_emitter(emitter_id)
    logger.info("Using emitter: %s", emitter_id)

    if emitter:
        # Use pluggable emitter
        for dt in registry.data_types.values():
            emitter.emit_type_header(dt, output_dir, registry=registry)
        for dt in registry.data_types.values():
            emitter.emit_converter(dt, config, output_dir, warning_module=warning_module)
        emitter.emit_factory(registry.data_types, output_dir)
        emitter.emit_platform_types(config, output_dir)
        if hasattr(emitter, 'emit_version_negotiation'):
            emitter.emit_version_negotiation(registry.data_types, output_dir)
    else:
        # Fallback to built-in generation
        for dt in registry.data_types.values():
            builtin_codegen.generate_data_type_header(dt, sentinel, output_dir, registry)
        for dt in registry.data_types.values():
            builtin_codegen.generate_converter(dt, config, output_dir, warning_module)
        builtin_codegen.generate_factory(registry.data_types, output_dir)
        builtin_codegen.copy_platform_types(config, output_dir)

    # Generate metadata
    builtin_codegen.generate_field_provenance(registry, output_dir)
    builtin_codegen.generate_version_overview(registry, output_dir)

    # Display warnings (FR-13)
    if warning_module.count() > 0:
        warning_module.display()

    logger.info("Generation complete. Output in %s", output_dir)
    print(f"Generation complete. Output in {output_dir}")


def run_verify(config_path: str, expected_dir: str, *,
               use_color: bool = True) -> None:
    """Verify generated output against expected golden files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_generate(config_path, tmpdir, use_color=use_color)

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


def _print_dry_run(registry, config, output_dir):
    """Print what files would be generated without writing anything."""
    emitter_id = config.get('emitter', 'cpp')
    print(f"Dry run: {len(registry.data_types)} type(s), emitter={emitter_id}")
    print(f"Output directory: {output_dir}")
    print()
    for type_name, dt in registry.data_types.items():
        versions = sorted(dt.versions.keys())
        print(f"  {type_name} ({len(versions)} version(s): {versions})")
        print(f"    data_types/{type_name}.h")
        print(f"    converters/generated/Converter_{type_name}.h")
        print(f"    converters/generated/Converter_{type_name}.cpp")
    print(f"    converters/generated/converters.cpp")
    print(f"    converters/generated/version_negotiation.h")
    print(f"    field_provenance.json")
    print(f"    version_overview.json")
    print()
    print(f"Total: {len(registry.data_types) * 3 + 4} file(s)")


def _get_emitter(emitter_id):
    """Get emitter by ID, returning None if not found (falls back to built-in)."""
    from ductape.emitters.emitter_base import get_emitter
    try:
        return get_emitter(emitter_id)
    except Exception:
        return None
