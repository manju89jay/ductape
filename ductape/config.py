"""YAML config loader with validation."""
from __future__ import annotations

import logging
import os
from typing import Any

import yaml

from ductape.exceptions import ConfigError

logger = logging.getLogger(__name__)


REQUIRED_TOP_LEVEL = {'project', 'header_sources', 'types'}
REQUIRED_PROJECT = {'name'}
VALID_FORMATS = {'c_header', 'protobuf', 'json_schema', 'multi_source'}
VALID_EMITTERS = {'cpp', 'python', 'rust', 'shared_lib'}
VALID_TYPE_KEYS = {
    'version_macro', 'defaults', 'renames', 'field_warnings',
    'enum_mappings', 'generate_reverse',
}
VALID_TOP_LEVEL_KEYS = {
    'project', 'header_sources', 'types', 'handcrafted',
    'additional_includes', 'warnings', 'preprocessor', 'format', 'emitter',
}


def load_config(config_path: str) -> dict[str, Any]:
    """Load and validate a config YAML file."""
    if not os.path.isfile(config_path):
        raise ConfigError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ConfigError("Config must be a YAML mapping")

    _validate(data, config_path)

    # Set defaults
    data.setdefault('handcrafted', [])
    data.setdefault('additional_includes', [])
    data.setdefault('warnings', {'min_display_severity': 1, 'color': True})
    data.setdefault('preprocessor', {'type': 'builtin'})
    data.setdefault('format', 'c_header')  # Parser frontend (FR-22)
    data.setdefault('emitter', 'cpp')       # Code emitter (FR-25)
    data['project'].setdefault('generic_version_sentinel', 9999)
    data['project'].setdefault('description', '')

    # Ensure type configs have defaults
    for type_name, type_cfg in data['types'].items():
        type_cfg.setdefault('defaults', {})
        type_cfg.setdefault('renames', {})
        type_cfg.setdefault('field_warnings', {})
        type_cfg.setdefault('enum_mappings', {})
        type_cfg.setdefault('generate_reverse', False)

    # Resolve paths relative to config file
    data['_config_dir'] = os.path.dirname(os.path.abspath(config_path))

    logger.debug("Loaded config: %d type(s), format=%s, emitter=%s",
                 len(data['types']), data['format'], data['emitter'])
    return data


def _validate(data: dict[str, Any], config_path: str) -> None:
    missing = REQUIRED_TOP_LEVEL - set(data.keys())
    if missing:
        raise ConfigError(f"Missing required top-level keys: {missing}")

    # Warn on unknown top-level keys
    unknown = set(data.keys()) - VALID_TOP_LEVEL_KEYS
    if unknown:
        logger.warning("Unknown top-level config keys (typo?): %s", unknown)

    # Validate format/emitter values
    fmt = data.get('format', 'c_header')
    if fmt not in VALID_FORMATS:
        raise ConfigError(
            f"Invalid format '{fmt}'. Must be one of: {sorted(VALID_FORMATS)}")

    emitter = data.get('emitter', 'cpp')
    if emitter not in VALID_EMITTERS:
        raise ConfigError(
            f"Invalid emitter '{emitter}'. Must be one of: {sorted(VALID_EMITTERS)}")

    # Validate project section
    if not isinstance(data['project'], dict):
        raise ConfigError("'project' must be a mapping")

    missing_proj = REQUIRED_PROJECT - set(data['project'].keys())
    if missing_proj:
        raise ConfigError(f"Missing required project keys: {missing_proj}")

    sentinel = data.get('project', {}).get('generic_version_sentinel', 9999)
    if not isinstance(sentinel, int) or sentinel <= 0:
        raise ConfigError("'project.generic_version_sentinel' must be a positive integer")

    # Validate header_sources
    if not isinstance(data['header_sources'], list):
        raise ConfigError("'header_sources' must be a list")

    if len(data['header_sources']) == 0:
        raise ConfigError("'header_sources' must not be empty")

    for i, src in enumerate(data['header_sources']):
        if not isinstance(src, dict) or 'path' not in src or 'version_tag' not in src:
            raise ConfigError(f"header_sources[{i}] must have 'path' and 'version_tag'")

    # Validate types
    if not isinstance(data['types'], dict):
        raise ConfigError("'types' must be a mapping")

    if len(data['types']) == 0:
        raise ConfigError("'types' must not be empty")

    for type_name, type_cfg in data['types'].items():
        if not isinstance(type_cfg, dict):
            raise ConfigError(f"types.{type_name} must be a mapping")
        if 'version_macro' not in type_cfg:
            raise ConfigError(f"types.{type_name} missing 'version_macro'")

        unknown_type_keys = set(type_cfg.keys()) - VALID_TYPE_KEYS
        if unknown_type_keys:
            logger.warning("types.%s: unknown keys (typo?): %s",
                           type_name, unknown_type_keys)

        # Validate sub-field types
        defaults = type_cfg.get('defaults', {})
        if defaults and not isinstance(defaults, dict):
            raise ConfigError(f"types.{type_name}.defaults must be a mapping")

        renames = type_cfg.get('renames', {})
        if renames and not isinstance(renames, dict):
            raise ConfigError(f"types.{type_name}.renames must be a mapping")
