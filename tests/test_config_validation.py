"""Tests for config validation."""

import os
import pytest
import tempfile
import yaml
from ductape.config import load_config, ConfigError


def _write_config(data):
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    yaml.dump(data, f)
    f.close()
    return f.name


def _minimal_config():
    return {
        'project': {'name': 'test'},
        'header_sources': [{'path': 'headers/v1', 'version_tag': 'v1'}],
        'types': {
            'Foo_t': {'version_macro': 'FOO_VERSION'}
        },
    }


def test_valid_config():
    path = _write_config(_minimal_config())
    cfg = load_config(path)
    assert cfg['project']['name'] == 'test'
    os.unlink(path)


def test_missing_project():
    data = _minimal_config()
    del data['project']
    path = _write_config(data)
    with pytest.raises(ConfigError, match="project"):
        load_config(path)
    os.unlink(path)


def test_missing_header_sources():
    data = _minimal_config()
    del data['header_sources']
    path = _write_config(data)
    with pytest.raises(ConfigError, match="header_sources"):
        load_config(path)
    os.unlink(path)


def test_missing_types():
    data = _minimal_config()
    del data['types']
    path = _write_config(data)
    with pytest.raises(ConfigError, match="types"):
        load_config(path)
    os.unlink(path)


def test_empty_types():
    data = _minimal_config()
    data['types'] = {}
    path = _write_config(data)
    with pytest.raises(ConfigError, match="empty"):
        load_config(path)
    os.unlink(path)


def test_missing_version_macro():
    data = _minimal_config()
    data['types']['Foo_t'] = {'defaults': {}}
    path = _write_config(data)
    with pytest.raises(ConfigError, match="version_macro"):
        load_config(path)
    os.unlink(path)


def test_defaults_set():
    path = _write_config(_minimal_config())
    cfg = load_config(path)
    assert cfg['project']['generic_version_sentinel'] == 9999
    assert cfg['types']['Foo_t']['defaults'] == {}
    assert cfg['types']['Foo_t']['renames'] == {}
    os.unlink(path)


def test_file_not_found():
    with pytest.raises(ConfigError, match="not found"):
        load_config("/nonexistent/config.yaml")


def test_load_reference_config():
    """Load the actual reference project config."""
    config_path = os.path.join(os.path.dirname(__file__), "..",
                               "variants/reference_project/config.yaml")
    cfg = load_config(config_path)
    assert cfg['project']['name'] == 'reference_project'
    assert 'TelemetryData_t' in cfg['types']
    assert 'CommandMessage_t' in cfg['types']
    assert 'SystemStatus_t' in cfg['types']
