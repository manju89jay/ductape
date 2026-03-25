"""Regression: compare output vs expected_output."""

import os
import tempfile
import filecmp
from ductape.codegen import run_generate


def test_golden_files_match():
    """Verify generated output matches expected golden files."""
    config_path = os.path.join(os.path.dirname(__file__), "..",
                               "variants/reference_project/config.yaml")
    expected_dir = os.path.join(os.path.dirname(__file__), "..",
                                "variants/reference_project/expected_output")

    with tempfile.TemporaryDirectory() as tmpdir:
        run_generate(config_path, tmpdir)

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

        assert differences == [], f"Golden file differences: {differences}"


def test_all_expected_files_exist():
    """Verify that all expected output files are present."""
    expected_dir = os.path.join(os.path.dirname(__file__), "..",
                                "variants/reference_project/expected_output")
    expected_files = [
        "data_types/TelemetryData_t.h",
        "data_types/CommandMessage_t.h",
        "data_types/SystemStatus_t.h",
        "data_types/platform_types.h",
        "converters/generated/Converter_TelemetryData_t.h",
        "converters/generated/Converter_TelemetryData_t.cpp",
        "converters/generated/Converter_CommandMessage_t.h",
        "converters/generated/Converter_CommandMessage_t.cpp",
        "converters/generated/Converter_SystemStatus_t.h",
        "converters/generated/Converter_SystemStatus_t.cpp",
        "converters/generated/converters.cpp",
        "field_provenance.json",
    ]
    for f in expected_files:
        assert os.path.isfile(os.path.join(expected_dir, f)), f"Missing: {f}"
