"""Tests for Phase 14: Advanced emitters + two-stage pipelines (FR-26, FR-27)."""

import os
import json
import tempfile
import pytest

from ductape.config import load_config
from ductape.codegen import run_generate
from ductape.emitters.emitter_base import get_emitter, list_emitters
from ductape.conv.type_registry import TypeRegistry
from ductape.conv.typecontainer import TypeContainer, CType, CTypeMember
from ductape.warnings import WarningModule
from ductape.two_stage import TwoStagePipeline, StageResult
from ductape.struct_diff import compute_struct_diff, format_struct_diff
from ductape.frontends.frontend_base import get_frontend


def _ref_config_path():
    return os.path.join(os.path.dirname(__file__), "..",
                        "variants/reference_project/config.yaml")


def _multi_format_dir():
    return os.path.join(os.path.dirname(__file__), "..",
                        "variants/reference_multi_format")


# ── FR-26: Shared library emitter ──────────────────────────────────


def test_shared_lib_emitter_registered():
    """SharedLibEmitter is auto-registered."""
    import ductape.emitters.shared_lib_emitter  # noqa: F401
    assert "shared_lib" in list_emitters()


def test_shared_lib_emitter_generates_files():
    """SharedLibEmitter generates C source files."""
    config = load_config(_ref_config_path())
    registry = TypeRegistry(config)
    registry.load_all()

    emitter = get_emitter("shared_lib")

    with tempfile.TemporaryDirectory() as tmpdir:
        for type_name, dt in registry.data_types.items():
            emitter.emit_type_header(dt, tmpdir, registry=registry)
            emitter.emit_converter(dt, config, tmpdir)

        emitter.emit_factory(registry.data_types, tmpdir)

        # Check generated files
        shared_dir = os.path.join(tmpdir, "shared_lib")
        assert os.path.isdir(shared_dir)
        assert os.path.isfile(os.path.join(shared_dir, "adapter_exports.h"))
        assert os.path.isfile(os.path.join(shared_dir, "TelemetryData_t_types.h"))
        assert os.path.isfile(os.path.join(shared_dir, "TelemetryData_t_converter.c"))


def test_shared_lib_exports_header_content():
    """adapter_exports.h contains correct function declarations."""
    config = load_config(_ref_config_path())
    registry = TypeRegistry(config)
    registry.load_all()

    emitter = get_emitter("shared_lib")

    with tempfile.TemporaryDirectory() as tmpdir:
        emitter.emit_factory(registry.data_types, tmpdir)
        with open(os.path.join(tmpdir, "shared_lib", "adapter_exports.h")) as f:
            content = f.read()

        assert "GetConverterVersion" in content
        assert "GetSupportedVersionCount" in content
        assert "GetSupportedVersions" in content
        assert "ConvertData" in content
        assert "TelemetryData_t" in content


def test_shared_lib_converter_has_abi_exports():
    """Converter C source has EXPORT macros and version functions."""
    config = load_config(_ref_config_path())
    registry = TypeRegistry(config)
    registry.load_all()

    emitter = get_emitter("shared_lib")

    with tempfile.TemporaryDirectory() as tmpdir:
        dt = registry.data_types["TelemetryData_t"]
        emitter.emit_converter(dt, config, tmpdir)

        with open(os.path.join(tmpdir, "shared_lib",
                               "TelemetryData_t_converter.c")) as f:
            content = f.read()

        assert "EXPORT" in content
        assert "TelemetryData_t_GetConverterVersion" in content
        assert "TelemetryData_t_ConvertData" in content
        assert "TelemetryData_t_GetSupportedVersions" in content
        assert "switch (src_version)" in content


def test_shared_lib_types_header_has_structs():
    """Types header has version-specific C structs."""
    config = load_config(_ref_config_path())
    registry = TypeRegistry(config)
    registry.load_all()

    emitter = get_emitter("shared_lib")

    with tempfile.TemporaryDirectory() as tmpdir:
        dt = registry.data_types["TelemetryData_t"]
        emitter.emit_type_header(dt, tmpdir, registry=registry)

        with open(os.path.join(tmpdir, "shared_lib",
                               "TelemetryData_t_types.h")) as f:
            content = f.read()

        assert "struct TelemetryData_t_v1" in content
        assert "struct TelemetryData_t_v2" in content
        assert "struct TelemetryData_t_v3" in content
        assert "struct TelemetryData_t_generic" in content
        assert "uint32_t timestamp" in content


def test_shared_lib_compiles():
    """Generated shared lib C source should compile."""
    config = load_config(_ref_config_path())
    registry = TypeRegistry(config)
    registry.load_all()

    emitter = get_emitter("shared_lib")

    with tempfile.TemporaryDirectory() as tmpdir:
        for dt in registry.data_types.values():
            emitter.emit_type_header(dt, tmpdir, registry=registry)
            emitter.emit_converter(dt, config, tmpdir)
        emitter.emit_factory(registry.data_types, tmpdir)

        shared_dir = os.path.join(tmpdir, "shared_lib")
        # Compile each .c file
        for fname in os.listdir(shared_dir):
            if fname.endswith('.c'):
                fpath = os.path.join(shared_dir, fname)
                ret = os.system(
                    f"gcc -c {fpath} -I{shared_dir} "
                    f"-o {os.path.join(tmpdir, fname + '.o')} "
                    f"-std=c11 -fPIC 2>/dev/null"
                )
                assert ret == 0, f"Failed to compile {fname}"


# ── FR-27: Two-stage adaptation pipeline ───────────────────────────


def test_two_stage_stage1_basic():
    """Stage 1 builds DataTypes from parsed containers."""
    frontend = get_frontend("protobuf")
    config = {'_config_dir': _multi_format_dir()}

    v1 = frontend.parse("schemas/sensor_v1.proto", config)
    v2 = frontend.parse("schemas/sensor_v2.proto", config)

    pipeline_config = {
        'sources': {
            'sensors': {
                'stage1': {
                    'hub_version': 'v2',
                    'types': {
                        'SensorReading': {
                            'version_field': 'schema_version',
                            'defaults': {'confidence': '0.0'},
                            'renames': {'speed': 'ground_speed'},
                        },
                    },
                },
            },
        },
    }

    pipeline = TwoStagePipeline(pipeline_config)
    result = pipeline.run_stage1(
        'sensors',
        pipeline_config['sources']['sensors'],
        [('v1', v1), ('v2', v2)],
    )

    assert 'SensorReading' in result.data_types
    dt = result.data_types['SensorReading']
    assert 1 in dt.versions
    assert 2 in dt.versions
    assert dt.generic is not None


def test_two_stage_stage1_generic_has_superset():
    """Stage 1 generic version is a superset of all fields."""
    frontend = get_frontend("protobuf")
    config = {'_config_dir': _multi_format_dir()}

    v1 = frontend.parse("schemas/sensor_v1.proto", config)
    v2 = frontend.parse("schemas/sensor_v2.proto", config)

    pipeline_config = {
        'sources': {
            'sensors': {
                'stage1': {
                    'types': {
                        'SensorReading': {
                            'renames': {'speed': 'ground_speed'},
                        },
                    },
                },
            },
        },
    }

    pipeline = TwoStagePipeline(pipeline_config)
    result = pipeline.run_stage1(
        'sensors',
        pipeline_config['sources']['sensors'],
        [('v1', v1), ('v2', v2)],
    )

    dt = result.data_types['SensorReading']
    gen_names = [m.name for m in dt.generic.ctype.members]
    # Should have all fields from both versions
    assert 'timestamp' in gen_names
    assert 'ground_speed' in gen_names  # renamed from speed
    assert 'confidence' in gen_names     # only in v2
    assert 'source_quality' in gen_names  # only in v2


def test_two_stage_stage2_mapping():
    """Stage 2 maps fields between format families."""
    frontend = get_frontend("protobuf")
    config = {'_config_dir': _multi_format_dir()}

    v1 = frontend.parse("schemas/sensor_v1.proto", config)
    v2 = frontend.parse("schemas/sensor_v2.proto", config)

    pipeline_config = {
        'sources': {
            'sensors': {
                'stage1': {
                    'types': {
                        'SensorReading': {
                            'renames': {'speed': 'ground_speed'},
                        },
                    },
                },
            },
        },
        'stage2': {
            'type_mappings': {
                'SensorReading': 'PlatformTrack_t',
            },
            'field_mappings': {
                'SensorReading': {
                    'latitude': 'lat',
                    'longitude': 'lon',
                    'ground_speed': 'velocity',
                    'altitude_m': 'alt_msl',
                },
            },
        },
    }

    pipeline = TwoStagePipeline(pipeline_config)

    # Run stage 1
    pipeline.run_stage1(
        'sensors',
        pipeline_config['sources']['sensors'],
        [('v1', v1), ('v2', v2)],
    )

    # Run stage 2
    result = pipeline.run_stage2(
        pipeline_config['stage2'],
        pipeline.stage1_results,
    )

    assert 'PlatformTrack_t' in result.data_types
    pt = result.data_types['PlatformTrack_t']
    assert pt.generic is not None

    mapped_names = [m.name for m in pt.generic.ctype.members]
    assert 'lat' in mapped_names       # mapped from latitude
    assert 'lon' in mapped_names       # mapped from longitude
    assert 'velocity' in mapped_names  # mapped from ground_speed
    assert 'alt_msl' in mapped_names   # mapped from altitude_m


def test_two_stage_full_pipeline():
    """Full pipeline run processes both stages."""
    frontend = get_frontend("protobuf")
    config = {'_config_dir': _multi_format_dir()}

    v1 = frontend.parse("schemas/sensor_v1.proto", config)
    v2 = frontend.parse("schemas/sensor_v2.proto", config)

    pipeline_config = {
        'sources': {
            'sensors': {
                'stage1': {
                    'types': {
                        'SensorReading': {
                            'renames': {'speed': 'ground_speed'},
                        },
                    },
                },
            },
        },
        'stage2': {
            'type_mappings': {'SensorReading': 'PlatformTrack_t'},
            'field_mappings': {'SensorReading': {'latitude': 'lat'}},
        },
    }

    pipeline = TwoStagePipeline(pipeline_config)
    results = pipeline.run({
        'sensors': {
            'config': pipeline_config['sources']['sensors'],
            'containers': [('v1', v1), ('v2', v2)],
        },
    })

    assert 'stage1' in results
    assert 'stage2' in results
    assert 'sensors' in results['stage1']
    assert 'PlatformTrack_t' in results['stage2'].data_types


def test_two_stage_provenance():
    """Pipeline produces provenance report."""
    frontend = get_frontend("protobuf")
    config = {'_config_dir': _multi_format_dir()}

    v1 = frontend.parse("schemas/sensor_v1.proto", config)
    v2 = frontend.parse("schemas/sensor_v2.proto", config)

    pipeline_config = {
        'sources': {
            'sensors': {
                'stage1': {
                    'types': {
                        'SensorReading': {'renames': {}},
                    },
                },
            },
        },
        'stage2': {
            'type_mappings': {'SensorReading': 'PlatformTrack_t'},
            'field_mappings': {'SensorReading': {}},
        },
    }

    pipeline = TwoStagePipeline(pipeline_config)
    pipeline.run({
        'sensors': {
            'config': pipeline_config['sources']['sensors'],
            'containers': [('v1', v1), ('v2', v2)],
        },
    })

    prov = pipeline.generate_provenance()
    assert 'stage1' in prov
    assert 'stage2' in prov
    assert 'sensors' in prov['stage1']
    assert 'SensorReading' in prov['stage1']['sensors']
    assert 'PlatformTrack_t' in prov['stage2']


def test_two_stage_missing_source_type_warns():
    """Stage 2 with missing source type adds a warning."""
    wm = WarningModule(min_severity=0, use_color=False)
    pipeline_config = {
        'sources': {},
        'stage2': {
            'type_mappings': {'NonExistent': 'Target_t'},
            'field_mappings': {},
        },
    }

    pipeline = TwoStagePipeline(pipeline_config, warning_module=wm)
    result = pipeline.run_stage2(
        pipeline_config['stage2'], {},
    )

    assert wm.has_errors()


# ── Structural diff ────────────────────────────────────────────────


def test_struct_diff_identical_dirs():
    """Identical directories report no differences."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_generate(_ref_config_path(), tmpdir)
        diff = compute_struct_diff(tmpdir, tmpdir)
        assert diff['only_in_dir1'] == []
        assert diff['only_in_dir2'] == []
        assert diff['differing'] == []
        assert len(diff['identical']) > 0


def test_struct_diff_different_dirs():
    """Different directories report differences."""
    with tempfile.TemporaryDirectory() as dir1:
        with tempfile.TemporaryDirectory() as dir2:
            run_generate(_ref_config_path(), dir1)
            run_generate(_ref_config_path(), dir2)

            # Modify a file in dir2
            mod_file = os.path.join(dir2, "version_overview.json")
            with open(mod_file, 'w') as f:
                json.dump({"modified": True}, f)

            diff = compute_struct_diff(dir1, dir2)
            assert "version_overview.json" in diff['differing']


def test_struct_diff_extra_files():
    """Extra files in one directory are reported."""
    with tempfile.TemporaryDirectory() as dir1:
        with tempfile.TemporaryDirectory() as dir2:
            run_generate(_ref_config_path(), dir1)
            run_generate(_ref_config_path(), dir2)

            # Add extra file to dir2
            with open(os.path.join(dir2, "extra.txt"), 'w') as f:
                f.write("extra")

            diff = compute_struct_diff(dir1, dir2)
            assert "extra.txt" in diff['only_in_dir2']


def test_struct_diff_format():
    """format_struct_diff produces readable output."""
    diff = {
        'only_in_dir1': ['old.h'],
        'only_in_dir2': ['new.h'],
        'differing': ['changed.cpp'],
        'identical': ['same.h'],
    }
    text = format_struct_diff(diff, "/a", "/b")
    assert "Only in dir1" in text
    assert "old.h" in text
    assert "Only in dir2" in text
    assert "new.h" in text
    assert "Differing" in text
    assert "changed.cpp" in text
    assert "Identical: 1 files" in text


# ── Integration: existing pipeline still works ─────────────────────


def test_existing_pipeline_unaffected():
    """Existing C++ pipeline still produces correct output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_generate(_ref_config_path(), tmpdir)
        assert os.path.isfile(os.path.join(tmpdir, "data_types", "TelemetryData_t.h"))
        assert os.path.isfile(os.path.join(tmpdir, "converters", "generated", "converters.cpp"))
        assert os.path.isfile(os.path.join(tmpdir, "version_overview.json"))


def test_all_emitters_registered():
    """All emitters (cpp + shared_lib) are discoverable."""
    emitters = list_emitters()
    assert "cpp" in emitters
    assert "shared_lib" in emitters
