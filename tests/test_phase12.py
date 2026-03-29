"""Tests for Phase 12: Pluggable architecture (FR-22, FR-25)."""

import os
import json
import tempfile
import pytest

from ductape.config import load_config
from ductape.codegen import run_generate
from ductape.frontends.frontend_base import (
    ParserFrontend, register_frontend, get_frontend, list_frontends,
    _FRONTEND_REGISTRY,
)
from ductape.emitters.emitter_base import (
    CodeEmitter, register_emitter, get_emitter, list_emitters,
    _EMITTER_REGISTRY,
)
from ductape.conv.typecontainer import TypeContainer


def _ref_config_path():
    return os.path.join(os.path.dirname(__file__), "..",
                        "variants/reference_project/config.yaml")


# ── FR-22: Parser frontend plugin architecture ─────────────────────


def test_c_header_frontend_registered():
    """CHeaderFrontend is auto-registered on import."""
    import ductape.frontends.c_header  # noqa: F401
    assert "c_header" in list_frontends()


def test_get_frontend_c_header():
    """get_frontend returns a CHeaderFrontend instance."""
    frontend = get_frontend("c_header")
    assert frontend.format_id == "c_header"
    assert '.h' in frontend.file_extensions()


def test_get_frontend_unknown_raises():
    """get_frontend raises ValueError for unknown format."""
    with pytest.raises(ValueError, match="Unknown parser frontend"):
        get_frontend("nonexistent_format")


def test_c_header_frontend_parses_directory():
    """CHeaderFrontend can parse a header directory like InterfaceVersion."""
    config = load_config(_ref_config_path())
    frontend = get_frontend("c_header")

    container = frontend.parse("headers/v1", config)

    assert isinstance(container, TypeContainer)
    assert "TelemetryData_t" in container.types
    assert "CommandMessage_t" in container.types


def test_c_header_frontend_parses_all_versions():
    """CHeaderFrontend can parse all three version directories."""
    config = load_config(_ref_config_path())
    frontend = get_frontend("c_header")

    for ver in ["headers/v1", "headers/v2", "headers/v3"]:
        container = frontend.parse(ver, config)
        assert "TelemetryData_t" in container.types


def test_register_custom_frontend():
    """Custom frontends can be registered and discovered."""
    # Save original registry state
    original = dict(_FRONTEND_REGISTRY)

    class TestFrontend(ParserFrontend):
        format_id = "test_format"

        def parse(self, schema_path, config):
            return TypeContainer()

        def file_extensions(self):
            return ['.test']

    register_frontend(TestFrontend)

    try:
        assert "test_format" in list_frontends()
        instance = get_frontend("test_format")
        assert instance.format_id == "test_format"
        assert instance.file_extensions() == ['.test']
    finally:
        # Restore registry
        _FRONTEND_REGISTRY.clear()
        _FRONTEND_REGISTRY.update(original)


def test_frontend_list_not_empty():
    """At least one frontend (c_header) is registered by default."""
    frontends = list_frontends()
    assert len(frontends) >= 1
    assert "c_header" in frontends


# ── FR-25: Code emitter plugin architecture ────────────────────────


def test_cpp_emitter_registered():
    """CppEmitter is auto-registered on import."""
    import ductape.emitters.cpp_emitter  # noqa: F401
    assert "cpp" in list_emitters()


def test_get_emitter_cpp():
    """get_emitter returns a CppEmitter instance."""
    emitter = get_emitter("cpp")
    assert emitter.emitter_id == "cpp"


def test_get_emitter_unknown_raises():
    """get_emitter raises ValueError for unknown emitter."""
    with pytest.raises(ValueError, match="Unknown code emitter"):
        get_emitter("nonexistent_emitter")


def test_register_custom_emitter():
    """Custom emitters can be registered and discovered."""
    original = dict(_EMITTER_REGISTRY)

    class TestEmitter(CodeEmitter):
        emitter_id = "test_emitter"

        def emit_type_header(self, data_type, output_dir, registry=None):
            pass

        def emit_converter(self, data_type, config, output_dir, warning_module=None):
            pass

        def emit_factory(self, data_types, output_dir):
            pass

    register_emitter(TestEmitter)

    try:
        assert "test_emitter" in list_emitters()
        instance = get_emitter("test_emitter")
        assert instance.emitter_id == "test_emitter"
    finally:
        _EMITTER_REGISTRY.clear()
        _EMITTER_REGISTRY.update(original)


def test_emitter_list_not_empty():
    """At least one emitter (cpp) is registered by default."""
    emitters = list_emitters()
    assert len(emitters) >= 1
    assert "cpp" in emitters


# ── Integration: CppEmitter produces same output as built-in ──────


def test_cpp_emitter_generates_all_files():
    """CppEmitter generates all expected output files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_generate(_ref_config_path(), tmpdir)

        # Data type headers
        assert os.path.isfile(os.path.join(tmpdir, "data_types", "TelemetryData_t.h"))
        assert os.path.isfile(os.path.join(tmpdir, "data_types", "CommandMessage_t.h"))
        assert os.path.isfile(os.path.join(tmpdir, "data_types", "SystemStatus_t.h"))

        # Converter files
        assert os.path.isfile(os.path.join(tmpdir, "converters", "generated", "Converter_TelemetryData_t.h"))
        assert os.path.isfile(os.path.join(tmpdir, "converters", "generated", "Converter_TelemetryData_t.cpp"))

        # Factory
        assert os.path.isfile(os.path.join(tmpdir, "converters", "generated", "converters.cpp"))

        # Platform types
        assert os.path.isfile(os.path.join(tmpdir, "data_types", "platform_types.h"))

        # Provenance and overview
        assert os.path.isfile(os.path.join(tmpdir, "field_provenance.json"))
        assert os.path.isfile(os.path.join(tmpdir, "version_overview.json"))


def test_cpp_emitter_output_compiles():
    """Generated C++ from CppEmitter should compile."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_generate(_ref_config_path(), tmpdir)

        # Compile check
        ret = os.system(
            f"g++ -c {tmpdir}/converters/generated/*.cpp "
            f"-I{tmpdir} -Iruntime_reference "
            f"-I{tmpdir}/converters/generated -std=c++17 2>/dev/null"
        )
        assert ret == 0, "Generated C++ should compile cleanly"


# ── Config defaults for format/emitter ─────────────────────────────


def test_config_defaults_format_and_emitter():
    """Config sets default format='c_header' and emitter='cpp'."""
    config = load_config(_ref_config_path())
    assert config['format'] == 'c_header'
    assert config['emitter'] == 'cpp'


# ── Existing behaviour unchanged ───────────────────────────────────


def test_existing_golden_files_still_match():
    """Golden file verification still passes with pluggable architecture."""
    from ductape.codegen import run_verify
    run_verify(_ref_config_path(),
               os.path.join(os.path.dirname(__file__), "..",
                            "variants/reference_project/expected_output"))
