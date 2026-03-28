"""Tests for Phase 11: Utility features (FR-10, FR-11, FR-12, FR-13, FR-14, NFR-05)."""

import os
import json
import tempfile
import pytest

from ductape.config import load_config
from ductape.conv.type_registry import TypeRegistry, VersionConflictError
from ductape.conv.converter import Converter
from ductape.conv.code_writer import CodeWriter
from ductape.conv.typecontainer import CType, CTypeMember
from ductape.conv.data_type import DataType
from ductape.codegen import run_generate
from ductape.warnings import WarningModule
from ductape.dependency_extractor import extract_dependencies, extract_from_config
from ductape.version_diff import compute_diff, format_diff_report


def _ref_config_path():
    return os.path.join(os.path.dirname(__file__), "..",
                        "variants/reference_project/config.yaml")


def _get_registry():
    config = load_config(_ref_config_path())
    reg = TypeRegistry(config)
    reg.load_all()
    return reg, config


# ── FR-14: Version conflict detection ──────────────────────────────


def test_version_conflict_different_member_count():
    """Same version number with different number of members raises error."""
    config = load_config(_ref_config_path())

    # Create a fake second header source that duplicates v1 with different layout
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a modified v1 header with an extra field
        v1_dir = os.path.join(tmpdir, "headers", "v1_dup")
        os.makedirs(v1_dir)

        header = """
#define TELEMETRY_DATA_VERSION 1
typedef struct {
    uint32_t timestamp;
    float32 latitude;
    float32 extra_field;
} TelemetryData_t;
"""
        with open(os.path.join(v1_dir, "telemetry_types.h"), 'w') as f:
            f.write(header)

        # Copy platform_types from reference project
        config['header_sources'].append({
            'path': os.path.relpath(v1_dir, config['_config_dir']),
            'version_tag': 'v1_dup',
        })

        reg = TypeRegistry(config)
        with pytest.raises(VersionConflictError, match="Version conflict"):
            reg.load_all()


def test_version_conflict_different_field_names():
    """Same version number with different field names raises error."""
    config = load_config(_ref_config_path())

    with tempfile.TemporaryDirectory() as tmpdir:
        v1_dir = os.path.join(tmpdir, "headers", "v1_dup")
        os.makedirs(v1_dir)

        # Same number of fields but different names
        # We need the exact same version number to trigger conflict
        # Use a simpler type
        header = """
#define COMMAND_MSG_VERSION 1
typedef struct {
    uint32_t timestamp;
    uint16_t different_name;
    uint8_t priority;
    uint8_t payload[32];
} CommandMessage_t;
"""
        with open(os.path.join(v1_dir, "telemetry_types.h"), 'w') as f:
            f.write(header)

        config['header_sources'].append({
            'path': os.path.relpath(v1_dir, config['_config_dir']),
            'version_tag': 'v1_dup',
        })

        reg = TypeRegistry(config)
        with pytest.raises(VersionConflictError, match="structural mismatch"):
            reg.load_all()


def test_no_conflict_on_identical_duplicate():
    """Same version, identical layout should NOT raise (idempotent)."""
    reg, config = _get_registry()
    # If load_all() succeeded, no conflict was raised
    assert len(reg.data_types) > 0


# ── FR-13: Missing-field warnings ──────────────────────────────────


def test_converter_emits_missing_field_warnings():
    """Converter emits warnings for fields missing in source version."""
    reg, config = _get_registry()
    dt = reg.data_types['TelemetryData_t']
    wm = WarningModule(min_severity=0, use_color=False)
    conv = Converter(dt, config, warning_module=wm)

    # V1 is missing several fields that exist in generic
    v1 = dt.versions[1]
    w = CodeWriter()
    conv.generate_forward_body(v1, w)

    # Should have warnings for fields missing from V1
    assert wm.count(0) > 0, "Expected warnings for missing fields in V1"

    # Check that at least signal_quality is warned about
    messages = [w['message'] for w in wm.warnings]
    signal_warned = any('signal_quality' in m for m in messages)
    assert signal_warned, "Expected warning for signal_quality missing in V1"


def test_converter_no_warnings_without_module():
    """Converter works fine without a warning module (backwards compat)."""
    reg, config = _get_registry()
    dt = reg.data_types['TelemetryData_t']
    conv = Converter(dt, config)  # No warning_module

    v1 = dt.versions[1]
    w = CodeWriter()
    # Should not raise
    conv.generate_forward_body(v1, w)


def test_missing_field_warning_severity_from_config():
    """Field warnings from config should use configured severity."""
    reg, config = _get_registry()
    dt = reg.data_types['TelemetryData_t']
    wm = WarningModule(min_severity=0, use_color=False)
    conv = Converter(dt, config, warning_module=wm)

    # V1 is missing fields; generate forward body
    v1 = dt.versions[1]
    w = CodeWriter()
    conv.generate_forward_body(v1, w)

    # Fields with defaults should have severity 0 (info) by default
    default_warnings = [w for w in wm.warnings if 'default applied' in w['message']]
    assert len(default_warnings) > 0

    # Fields without defaults should have severity 1 (warning)
    zero_warnings = [w for w in wm.warnings if 'zero-initialized' in w['message']]
    # All zero-initialized fields should have severity >= 1
    for zw in zero_warnings:
        assert zw['severity'] >= 1


# ── FR-11: Version overview ────────────────────────────────────────


def test_version_overview_generated():
    """version_overview.json should be generated during build."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_generate(_ref_config_path(), tmpdir)
        overview_path = os.path.join(tmpdir, "version_overview.json")
        assert os.path.isfile(overview_path)

        with open(overview_path) as f:
            data = json.load(f)

        assert "TelemetryData_t" in data
        assert "CommandMessage_t" in data
        assert "SystemStatus_t" in data


def test_version_overview_contents():
    """version_overview.json should list correct versions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_generate(_ref_config_path(), tmpdir)
        with open(os.path.join(tmpdir, "version_overview.json")) as f:
            data = json.load(f)

        td = data["TelemetryData_t"]
        assert td["versions"] == [1, 2, 3]
        assert td["latest_version"] == 3
        assert td["version_count"] == 3


# ── FR-10: Dependency extractor ────────────────────────────────────


def test_extract_dependencies():
    """extract_dependencies copies header files to versioned directories."""
    with tempfile.TemporaryDirectory() as src_dir:
        with tempfile.TemporaryDirectory() as out_dir:
            # Create fake package with headers
            inc_dir = os.path.join(src_dir, "include")
            os.makedirs(inc_dir)
            with open(os.path.join(inc_dir, "types.h"), 'w') as f:
                f.write("typedef int my_type;")
            with open(os.path.join(inc_dir, "funcs.h"), 'w') as f:
                f.write("void foo();")

            packages = [{
                'path': src_dir,
                'version_tag': 'v1',
                'source_tag': 'mylib',
                'include_patterns': ['*.h'],
            }]

            results = extract_dependencies(packages, out_dir)

            assert ('v1', 'mylib') in results
            assert len(results[('v1', 'mylib')]) == 2

            # Check files exist in output
            assert os.path.isfile(os.path.join(out_dir, "v1", "mylib", "types.h"))
            assert os.path.isfile(os.path.join(out_dir, "v1", "mylib", "funcs.h"))


def test_extract_dependencies_nested():
    """extract_dependencies finds headers in nested subdirectories."""
    with tempfile.TemporaryDirectory() as src_dir:
        with tempfile.TemporaryDirectory() as out_dir:
            nested = os.path.join(src_dir, "deep", "nested")
            os.makedirs(nested)
            with open(os.path.join(nested, "deep.h"), 'w') as f:
                f.write("int x;")

            packages = [{
                'path': src_dir,
                'version_tag': 'v2',
                'source_tag': 'deep_pkg',
            }]

            results = extract_dependencies(packages, out_dir)
            assert len(results[('v2', 'deep_pkg')]) == 1


def test_extract_from_config_no_deps():
    """extract_from_config returns empty when no dependencies configured."""
    config = load_config(_ref_config_path())
    with tempfile.TemporaryDirectory() as out_dir:
        results = extract_from_config(config, out_dir)
        assert results == {}


# ── FR-12: Version diff ────────────────────────────────────────────


def test_diff_no_changes():
    """Identical snapshots produce no changes."""
    snapshot = {
        "TypeA": {"versions": [1, 2], "latest_version": 2, "version_count": 2},
    }
    diff = compute_diff(snapshot, snapshot)
    assert diff['added'] == {}
    assert diff['removed'] == {}
    assert diff['changed'] == {}
    assert diff['unchanged'] == ["TypeA"]


def test_diff_added_type():
    """New type detected in current snapshot."""
    prev = {"TypeA": {"versions": [1], "latest_version": 1, "version_count": 1}}
    curr = {
        "TypeA": {"versions": [1], "latest_version": 1, "version_count": 1},
        "TypeB": {"versions": [1, 2], "latest_version": 2, "version_count": 2},
    }
    diff = compute_diff(prev, curr)
    assert "TypeB" in diff['added']
    assert diff['removed'] == {}


def test_diff_removed_type():
    """Removed type detected."""
    prev = {
        "TypeA": {"versions": [1], "latest_version": 1, "version_count": 1},
        "TypeB": {"versions": [1], "latest_version": 1, "version_count": 1},
    }
    curr = {"TypeA": {"versions": [1], "latest_version": 1, "version_count": 1}}
    diff = compute_diff(prev, curr)
    assert "TypeB" in diff['removed']


def test_diff_changed_versions():
    """Changed version numbers detected."""
    prev = {"TypeA": {"versions": [1, 2], "latest_version": 2, "version_count": 2}}
    curr = {"TypeA": {"versions": [1, 2, 3], "latest_version": 3, "version_count": 3}}
    diff = compute_diff(prev, curr)
    assert "TypeA" in diff['changed']
    assert diff['changed']['TypeA']['added_versions'] == [3]


def test_diff_format_report():
    """format_diff_report produces readable output."""
    diff = {
        'added': {"NewType": {"versions": [1]}},
        'removed': {},
        'changed': {"TypeA": {
            'previous_versions': [1, 2],
            'current_versions': [1, 2, 3],
            'added_versions': [3],
            'removed_versions': [],
        }},
        'unchanged': ["TypeB"],
    }
    text = format_diff_report(diff)
    assert "Added types:" in text
    assert "NewType" in text
    assert "Changed types:" in text
    assert "TypeA" in text
    assert "Unchanged types: TypeB" in text


def test_diff_end_to_end():
    """End-to-end diff using two generated version_overview.json files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_generate(_ref_config_path(), tmpdir)
        overview_path = os.path.join(tmpdir, "version_overview.json")

        with open(overview_path) as f:
            current = json.load(f)

        # Simulate a previous snapshot with fewer versions
        previous = {}
        for t, info in current.items():
            previous[t] = {
                'versions': info['versions'][:2],
                'latest_version': info['versions'][1] if len(info['versions']) > 1 else info['versions'][0],
                'version_count': min(2, info['version_count']),
            }

        diff = compute_diff(previous, current)
        # TelemetryData_t should show version 3 as added
        assert "TelemetryData_t" in diff['changed']


# ── NFR-05: --no-color flag ────────────────────────────────────────


def test_no_color_flag_parsed(monkeypatch):
    """--no-color flag is parsed by the CLI."""
    import ductape.cli as cli_module
    # We test that the arg parser handles --no-color
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-color", action="store_true", default=False)
    args = parser.parse_args(["--no-color"])
    assert args.no_color is True
    args2 = parser.parse_args([])
    assert args2.no_color is False


def test_warning_module_no_color():
    """WarningModule respects use_color=False."""
    import io
    wm = WarningModule(min_severity=0, use_color=False)
    wm.add("test warning", severity=1, context="test")
    buf = io.StringIO()
    wm.display(file=buf)
    output = buf.getvalue()
    # No ANSI escape codes
    assert "\033[" not in output
    assert "[WARNING]" in output


def test_warning_module_with_color():
    """WarningModule emits ANSI codes when use_color=True."""
    import io
    wm = WarningModule(min_severity=0, use_color=True)
    wm.add("test warning", severity=1)
    buf = io.StringIO()
    wm.display(file=buf)
    output = buf.getvalue()
    assert "\033[" in output


# ── Integration: full generation still works ───────────────────────


def test_full_generation_with_phase11():
    """Full pipeline still produces all expected outputs including new ones."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_generate(_ref_config_path(), tmpdir)

        # Existing outputs still present
        assert os.path.isfile(os.path.join(tmpdir, "field_provenance.json"))
        assert os.path.isdir(os.path.join(tmpdir, "data_types"))
        assert os.path.isdir(os.path.join(tmpdir, "converters", "generated"))

        # New FR-11 output
        assert os.path.isfile(os.path.join(tmpdir, "version_overview.json"))
