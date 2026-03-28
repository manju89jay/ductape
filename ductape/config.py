"""YAML config loader with validation."""

import yaml
import os


REQUIRED_TOP_LEVEL = {'project', 'header_sources', 'types'}
REQUIRED_PROJECT = {'name'}


class ConfigError(Exception):
    pass


def load_config(config_path):
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

    return data


def _validate(data, config_path):
    missing = REQUIRED_TOP_LEVEL - set(data.keys())
    if missing:
        raise ConfigError(f"Missing required top-level keys: {missing}")

    if not isinstance(data['project'], dict):
        raise ConfigError("'project' must be a mapping")

    missing_proj = REQUIRED_PROJECT - set(data['project'].keys())
    if missing_proj:
        raise ConfigError(f"Missing required project keys: {missing_proj}")

    if not isinstance(data['header_sources'], list):
        raise ConfigError("'header_sources' must be a list")

    if len(data['header_sources']) == 0:
        raise ConfigError("'header_sources' must not be empty")

    for i, src in enumerate(data['header_sources']):
        if not isinstance(src, dict) or 'path' not in src or 'version_tag' not in src:
            raise ConfigError(f"header_sources[{i}] must have 'path' and 'version_tag'")

    if not isinstance(data['types'], dict):
        raise ConfigError("'types' must be a mapping")

    if len(data['types']) == 0:
        raise ConfigError("'types' must not be empty")

    for type_name, type_cfg in data['types'].items():
        if not isinstance(type_cfg, dict):
            raise ConfigError(f"types.{type_name} must be a mapping")
        if 'version_macro' not in type_cfg:
            raise ConfigError(f"types.{type_name} missing 'version_macro'")
