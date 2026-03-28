"""Tests for Phase 13: Additional format support (FR-23, FR-24)."""

import os
import json
import tempfile
import pytest

from ductape.conv.typecontainer import TypeContainer
from ductape.frontends.frontend_base import get_frontend, list_frontends


def _multi_format_dir():
    return os.path.join(os.path.dirname(__file__), "..",
                        "variants/reference_multi_format")


# ── FR-23: Protobuf .proto parsing ─────────────────────────────────


def test_protobuf_frontend_registered():
    """Protobuf frontend is auto-registered."""
    import ductape.frontends.protobuf  # noqa: F401
    assert "protobuf" in list_frontends()


def test_protobuf_frontend_file_extensions():
    frontend = get_frontend("protobuf")
    assert '.proto' in frontend.file_extensions()


def test_protobuf_parse_message():
    """Protobuf frontend parses message definitions into structs."""
    frontend = get_frontend("protobuf")
    config = {'_config_dir': _multi_format_dir()}
    container = frontend.parse("schemas/sensor_v1.proto", config)

    assert isinstance(container, TypeContainer)
    assert "SensorReading" in container.types
    sr = container.types["SensorReading"]
    assert sr.is_struct

    member_names = [m.name for m in sr.members]
    assert "timestamp" in member_names
    assert "latitude" in member_names
    assert "longitude" in member_names
    assert "speed" in member_names
    assert "altitude_m" in member_names
    assert "sensor_id" in member_names


def test_protobuf_parse_enum():
    """Protobuf frontend parses enum definitions."""
    frontend = get_frontend("protobuf")
    config = {'_config_dir': _multi_format_dir()}
    container = frontend.parse("schemas/sensor_v1.proto", config)

    assert "SensorStatus" in container.types
    ss = container.types["SensorStatus"]
    assert ss.is_enum
    enum_names = [v[0] for v in ss.enum_values]
    assert "UNKNOWN" in enum_names
    assert "ACTIVE" in enum_names
    assert "ERROR" in enum_names


def test_protobuf_parse_v2_has_more_fields():
    """V2 proto has additional fields (confidence, source_quality)."""
    frontend = get_frontend("protobuf")
    config = {'_config_dir': _multi_format_dir()}
    v1 = frontend.parse("schemas/sensor_v1.proto", config)
    v2 = frontend.parse("schemas/sensor_v2.proto", config)

    v1_names = {m.name for m in v1.types["SensorReading"].members}
    v2_names = {m.name for m in v2.types["SensorReading"].members}

    assert "confidence" not in v1_names
    assert "confidence" in v2_names
    assert "source_quality" in v2_names


def test_protobuf_parse_repeated_field():
    """Repeated fields are mapped as arrays."""
    frontend = get_frontend("protobuf")
    proto_text = """
syntax = "proto3";
message DataPacket {
  repeated float values = 1;
  uint32 count = 2;
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.proto',
                                     delete=False) as f:
        f.write(proto_text)
        f.flush()
        config = {'_config_dir': os.path.dirname(f.name)}
        container = frontend.parse(f.name, config)
    os.unlink(f.name)

    dp = container.types["DataPacket"]
    values_member = None
    for m in dp.members:
        if m.name == "values":
            values_member = m
            break
    assert values_member is not None
    assert values_member.is_array
    assert len(values_member.dimensions) > 0


def test_protobuf_parse_oneof():
    """Oneof fields produce a discriminator + variant fields."""
    frontend = get_frontend("protobuf")
    proto_text = """
syntax = "proto3";
message Event {
  uint32 id = 1;
  oneof payload {
    float measurement = 2;
    uint32 counter = 3;
  }
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.proto',
                                     delete=False) as f:
        f.write(proto_text)
        f.flush()
        config = {'_config_dir': os.path.dirname(f.name)}
        container = frontend.parse(f.name, config)
    os.unlink(f.name)

    ev = container.types["Event"]
    member_names = [m.name for m in ev.members]
    assert "id" in member_names
    assert "payload_case" in member_names  # discriminator
    assert "measurement" in member_names
    assert "counter" in member_names


def test_protobuf_parse_nested_message():
    """Nested messages are flattened as separate types."""
    frontend = get_frontend("protobuf")
    proto_text = """
syntax = "proto3";
message Outer {
  message Inner {
    uint32 x = 1;
    uint32 y = 2;
  }
  Inner position = 1;
  uint32 id = 2;
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.proto',
                                     delete=False) as f:
        f.write(proto_text)
        f.flush()
        config = {'_config_dir': os.path.dirname(f.name)}
        container = frontend.parse(f.name, config)
    os.unlink(f.name)

    assert "Inner" in container.types
    assert "Outer" in container.types


def test_protobuf_parse_map_field():
    """Map fields create entry struct and array member."""
    frontend = get_frontend("protobuf")
    proto_text = """
syntax = "proto3";
message Config {
  map<uint32, float> settings = 1;
  uint32 count = 2;
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.proto',
                                     delete=False) as f:
        f.write(proto_text)
        f.flush()
        config = {'_config_dir': os.path.dirname(f.name)}
        container = frontend.parse(f.name, config)
    os.unlink(f.name)

    cfg = container.types["Config"]
    member_names = [m.name for m in cfg.members]
    assert "settings" in member_names
    assert "settings_entry_t" in container.types


def test_protobuf_parse_directory():
    """Protobuf frontend can parse a directory of .proto files."""
    frontend = get_frontend("protobuf")
    config = {'_config_dir': _multi_format_dir()}
    container = frontend.parse("schemas", config)

    # Should find types from both proto files
    assert "SensorReading" in container.types
    assert "SensorStatus" in container.types


# ── FR-24: JSON Schema parsing ─────────────────────────────────────


def test_json_schema_frontend_registered():
    """JSON Schema frontend is auto-registered."""
    import ductape.frontends.json_schema  # noqa: F401
    assert "json_schema" in list_frontends()


def test_json_schema_frontend_file_extensions():
    frontend = get_frontend("json_schema")
    assert '.json' in frontend.file_extensions()


def test_json_schema_parse_object():
    """JSON Schema frontend parses object types into structs."""
    frontend = get_frontend("json_schema")
    config = {'_config_dir': _multi_format_dir()}
    container = frontend.parse("schemas/telemetry.json", config)

    assert "TelemetryPacket" in container.types
    tp = container.types["TelemetryPacket"]
    assert tp.is_struct

    member_names = [m.name for m in tp.members]
    assert "timestamp" in member_names
    assert "velocity" in member_names
    assert "position" in member_names


def test_json_schema_parse_ref():
    """$ref references are resolved to struct members."""
    frontend = get_frontend("json_schema")
    config = {'_config_dir': _multi_format_dir()}
    container = frontend.parse("schemas/telemetry.json", config)

    # GeoPosition should be parsed from definitions
    assert "GeoPosition" in container.types
    gp = container.types["GeoPosition"]
    assert gp.is_struct
    gp_names = [m.name for m in gp.members]
    assert "lat" in gp_names
    assert "lon" in gp_names
    assert "alt_msl" in gp_names

    # TelemetryPacket.position should reference GeoPosition
    tp = container.types["TelemetryPacket"]
    pos_member = None
    for m in tp.members:
        if m.name == "position":
            pos_member = m
            break
    assert pos_member is not None
    assert pos_member.is_struct
    assert pos_member.type_name == "GeoPosition"


def test_json_schema_parse_array():
    """Array properties are mapped with correct dimensions."""
    frontend = get_frontend("json_schema")
    config = {'_config_dir': _multi_format_dir()}
    container = frontend.parse("schemas/telemetry.json", config)

    tp = container.types["TelemetryPacket"]
    readings_member = None
    for m in tp.members:
        if m.name == "readings":
            readings_member = m
            break
    assert readings_member is not None
    assert readings_member.is_array
    assert readings_member.dimensions == [16]  # maxItems from schema


def test_json_schema_parse_enum():
    """Enum properties create enum types."""
    frontend = get_frontend("json_schema")
    config = {'_config_dir': _multi_format_dir()}
    container = frontend.parse("schemas/telemetry.json", config)

    # status enum should be created
    assert "status_enum_t" in container.types
    se = container.types["status_enum_t"]
    assert se.is_enum


def test_json_schema_parse_inline_object():
    """Inline object definitions create nested struct types."""
    schema = {
        "title": "Wrapper",
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "metadata": {
                "type": "object",
                "title": "MetadataInfo",
                "properties": {
                    "source": {"type": "string"},
                    "priority": {"type": "integer"},
                },
            },
        },
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json',
                                     delete=False) as f:
        json.dump(schema, f)
        f.flush()
        frontend = get_frontend("json_schema")
        config = {'_config_dir': os.path.dirname(f.name)}
        container = frontend.parse(f.name, config)
    os.unlink(f.name)

    assert "Wrapper" in container.types
    assert "MetadataInfo" in container.types
    mi = container.types["MetadataInfo"]
    assert mi.is_struct
    mi_names = [m.name for m in mi.members]
    assert "source" in mi_names
    assert "priority" in mi_names


def test_json_schema_string_property():
    """String properties map to uint8 arrays."""
    schema = {
        "title": "Person",
        "type": "object",
        "properties": {
            "name": {"type": "string", "maxLength": 128},
        },
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json',
                                     delete=False) as f:
        json.dump(schema, f)
        f.flush()
        frontend = get_frontend("json_schema")
        config = {'_config_dir': os.path.dirname(f.name)}
        container = frontend.parse(f.name, config)
    os.unlink(f.name)

    person = container.types["Person"]
    name_member = person.members[0]
    assert name_member.name == "name"
    assert name_member.is_array
    assert name_member.dimensions == [128]


# ── Integration: all frontends registered ──────────────────────────


def test_all_phase13_frontends_registered():
    """All Phase 13 frontends are discoverable."""
    frontends = list_frontends()
    assert "c_header" in frontends
    assert "protobuf" in frontends
    assert "json_schema" in frontends
