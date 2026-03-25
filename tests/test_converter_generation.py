"""Tests for converter generation."""

import os
import tempfile
import pytest
from ductape.config import load_config
from ductape.conv.type_registry import TypeRegistry
from ductape.conv.converter import Converter
from ductape.conv.code_writer import CodeWriter
from ductape.codegen import run_generate


@pytest.fixture
def registry():
    config_path = os.path.join(os.path.dirname(__file__), "..",
                               "variants/reference_project/config.yaml")
    config = load_config(config_path)
    reg = TypeRegistry(config)
    reg.load_all()
    return reg, config


def test_generate_creates_data_type_headers(registry):
    reg, config = registry
    with tempfile.TemporaryDirectory() as tmpdir:
        run_generate(os.path.join(os.path.dirname(__file__), "..",
                     "variants/reference_project/config.yaml"), tmpdir)
        assert os.path.isfile(os.path.join(tmpdir, "data_types", "TelemetryData_t.h"))
        assert os.path.isfile(os.path.join(tmpdir, "data_types", "CommandMessage_t.h"))
        assert os.path.isfile(os.path.join(tmpdir, "data_types", "SystemStatus_t.h"))


def test_generate_creates_converter_files(registry):
    reg, config = registry
    with tempfile.TemporaryDirectory() as tmpdir:
        run_generate(os.path.join(os.path.dirname(__file__), "..",
                     "variants/reference_project/config.yaml"), tmpdir)
        assert os.path.isfile(os.path.join(tmpdir, "converters", "generated", "Converter_TelemetryData_t.cpp"))
        assert os.path.isfile(os.path.join(tmpdir, "converters", "generated", "Converter_TelemetryData_t.h"))


def test_generate_creates_factory(registry):
    reg, config = registry
    with tempfile.TemporaryDirectory() as tmpdir:
        run_generate(os.path.join(os.path.dirname(__file__), "..",
                     "variants/reference_project/config.yaml"), tmpdir)
        factory_path = os.path.join(tmpdir, "converters", "generated", "converters.cpp")
        assert os.path.isfile(factory_path)
        with open(factory_path) as f:
            content = f.read()
        assert "GetGeneratedAdapters" in content


def test_converter_forward_body():
    """Test that forward converter body is generated."""
    config_path = os.path.join(os.path.dirname(__file__), "..",
                               "variants/reference_project/config.yaml")
    config = load_config(config_path)
    reg = TypeRegistry(config)
    reg.load_all()

    dt = reg.data_types["TelemetryData_t"]
    conv = Converter(dt, config)
    w = CodeWriter()
    conv.generate_forward_body(dt.versions[1], w)
    content = w.get_content()
    assert "memset" in content
    assert "dest.timestamp" in content


def test_converter_structural_identity():
    """Test structural identity check."""
    config_path = os.path.join(os.path.dirname(__file__), "..",
                               "variants/reference_project/config.yaml")
    config = load_config(config_path)
    reg = TypeRegistry(config)
    reg.load_all()

    dt = reg.data_types["TelemetryData_t"]
    conv = Converter(dt, config)
    # V1 and generic should NOT be identical
    assert not conv.are_structurally_identical(dt.versions[1], dt.generic)


def test_converter_rename_handling():
    """Test that renames are handled in conversion."""
    config_path = os.path.join(os.path.dirname(__file__), "..",
                               "variants/reference_project/config.yaml")
    config = load_config(config_path)
    reg = TypeRegistry(config)
    reg.load_all()

    dt = reg.data_types["TelemetryData_t"]
    conv = Converter(dt, config)
    w = CodeWriter()
    conv.generate_forward_body(dt.versions[1], w)
    content = w.get_content()
    # V1 has "speed", generic has "ground_speed" (renamed)
    assert "source.speed" in content
    assert "dest.ground_speed" in content


def test_converter_array_min_copy():
    """Test array min-dimension copy generation."""
    config_path = os.path.join(os.path.dirname(__file__), "..",
                               "variants/reference_project/config.yaml")
    config = load_config(config_path)
    reg = TypeRegistry(config)
    reg.load_all()

    dt = reg.data_types["TelemetryData_t"]
    conv = Converter(dt, config)
    w = CodeWriter()
    # V1 has payload[32], generic has payload[64]
    conv.generate_forward_body(dt.versions[1], w)
    content = w.get_content()
    assert "for (int i = 0; i < " in content
    assert "payload[i]" in content


def test_data_type_header_content():
    """Test generated header has correct structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(os.path.dirname(__file__), "..",
                                   "variants/reference_project/config.yaml")
        run_generate(config_path, tmpdir)
        header_path = os.path.join(tmpdir, "data_types", "TelemetryData_t.h")
        with open(header_path) as f:
            content = f.read()
        assert "#pragma once" in content
        assert "namespace TelemetryData_t_V_1" in content
        assert "namespace TelemetryData_t_V_2" in content
        assert "namespace TelemetryData_t_V_3" in content
        assert "namespace TelemetryData_t_V_Gen" in content
        assert "platform_types.h" in content
