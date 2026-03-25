"""Tests for semantic conflict detection and field provenance."""

import os
import json
import tempfile
from ductape.config import load_config
from ductape.conv.type_registry import TypeRegistry
from ductape.conv.field_provenance import generate_provenance
from ductape.codegen import run_generate
from ductape.warnings import WarningModule


def _get_registry():
    config_path = os.path.join(os.path.dirname(__file__), "..",
                               "variants/reference_project/config.yaml")
    config = load_config(config_path)
    reg = TypeRegistry(config)
    reg.load_all()
    return reg, config


def test_provenance_has_all_types():
    reg, config = _get_registry()
    prov = generate_provenance(reg)
    assert "TelemetryData_t" in prov
    assert "CommandMessage_t" in prov
    assert "SystemStatus_t" in prov


def test_provenance_version_mappings():
    reg, config = _get_registry()
    prov = generate_provenance(reg)
    telemetry = prov["TelemetryData_t"]
    # timestamp should be in all 3 versions
    ts = telemetry["timestamp"]
    assert "1" in ts["versions"]
    assert "2" in ts["versions"]
    assert "3" in ts["versions"]
    assert ts["type_compatible"] is True


def test_provenance_rename_tracking():
    reg, config = _get_registry()
    prov = generate_provenance(reg)
    telemetry = prov["TelemetryData_t"]
    # ground_speed was "speed" in V1 and V2
    gs = telemetry["ground_speed"]
    assert gs["versions"]["1"]["rename_from"] == "speed"
    assert gs["versions"]["2"]["rename_from"] == "speed"
    # V3 uses ground_speed directly
    assert "rename_from" not in gs["versions"]["3"]


def test_provenance_defaults_tracked():
    reg, config = _get_registry()
    prov = generate_provenance(reg)
    telemetry = prov["TelemetryData_t"]
    # signal_quality not in V1, should have default_applied_for
    sq = telemetry["signal_quality"]
    assert 1 in sq.get("default_applied_for", [])


def test_provenance_field_warnings():
    reg, config = _get_registry()
    prov = generate_provenance(reg)
    telemetry = prov["TelemetryData_t"]
    # op_status has a field warning
    ops = telemetry["op_status"]
    assert len(ops["warnings"]) > 0
    assert ops["warnings"][0]["severity"] == 1


def test_field_provenance_json_generated():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(os.path.dirname(__file__), "..",
                                   "variants/reference_project/config.yaml")
        run_generate(config_path, tmpdir)
        prov_path = os.path.join(tmpdir, "field_provenance.json")
        assert os.path.isfile(prov_path)
        with open(prov_path) as f:
            data = json.load(f)
        assert "TelemetryData_t" in data
        assert "CommandMessage_t" in data
        assert "SystemStatus_t" in data


def test_warning_module():
    wm = WarningModule(min_severity=1, use_color=False)
    wm.add("info message", severity=0)
    wm.add("warning message", severity=1)
    wm.add("error message", severity=2)
    assert wm.count(0) == 3
    assert wm.count(1) == 2
    assert wm.count(2) == 1
    assert wm.has_errors()
