"""Tests for C parser."""

import os
from ductape.conv.parser import Parser


def test_simple_struct():
    src = """
    typedef struct {
        uint32 x;
        uint32 y;
    } Point_t;
    """
    p = Parser()
    tc = p.parse(src)
    assert "Point_t" in tc.types
    assert tc.types["Point_t"].is_struct
    assert tc.types["Point_t"].member_count() == 2


def test_struct_with_array():
    src = """
    #define SIZE 10
    typedef struct {
        uint8 data[SIZE];
        uint32 count;
    } Buffer_t;
    """
    p = Parser()
    tc = p.parse(src)
    assert "Buffer_t" in tc.types
    buf = tc.types["Buffer_t"]
    assert buf.members[0].is_array
    assert buf.members[0].dimensions == [10]


def test_enum():
    src = """
    typedef enum {
        STATE_IDLE = 0,
        STATE_RUNNING,
        STATE_ERROR = 5,
        STATE_DONE
    } State_t;
    """
    p = Parser()
    tc = p.parse(src)
    assert "State_t" in tc.types
    assert tc.types["State_t"].is_enum
    vals = dict(tc.types["State_t"].enum_values)
    assert vals["STATE_IDLE"] == 0
    assert vals["STATE_RUNNING"] == 1
    assert vals["STATE_ERROR"] == 5
    assert vals["STATE_DONE"] == 6


def test_typedef_alias():
    src = "typedef uint32 MyUint;"
    p = Parser()
    tc = p.parse(src)
    assert "MyUint" in tc.types
    assert tc.types["MyUint"].aliased_type == "uint32"


def test_defines_captured():
    src = """
    #define VERSION 3
    #define BUF_SIZE 64
    """
    p = Parser()
    tc = p.parse(src)
    assert tc.defines["VERSION"] == 3
    assert tc.defines["BUF_SIZE"] == 64


def test_nested_struct():
    src = """
    typedef struct {
        float32 voltage;
        float32 current;
    } BatteryInfo_t;

    typedef struct {
        uint32 timestamp;
        BatteryInfo_t battery;
    } TelemetryData_t;
    """
    p = Parser()
    tc = p.parse(src)
    assert "BatteryInfo_t" in tc.types
    assert "TelemetryData_t" in tc.types
    td = tc.types["TelemetryData_t"]
    assert td.member_count() == 2
    assert td.members[1].type_name == "BatteryInfo_t"


def test_comments_stripped():
    src = """
    // This is a comment
    typedef struct {
        uint32 x; /* inline comment */
    } Foo_t;
    """
    p = Parser()
    tc = p.parse(src)
    assert "Foo_t" in tc.types


def test_cpp_style_struct():
    src = """
    struct MyStruct {
        uint32 value;
        float32 ratio;
    };
    """
    p = Parser()
    tc = p.parse(src)
    assert "MyStruct" in tc.types
    assert tc.types["MyStruct"].is_struct
    assert tc.types["MyStruct"].member_count() == 2


def test_forward_declaration():
    src = "struct ForwardDecl;"
    p = Parser()
    tc = p.parse(src)
    # Should not crash, forward decl not added as full type
    assert "ForwardDecl" not in tc.types


def test_tagged_typedef():
    src = """
    typedef struct TagName {
        uint32 a;
        uint32 b;
    } AliasName;
    """
    p = Parser()
    tc = p.parse(src)
    assert "AliasName" in tc.types
    assert tc.types["AliasName"].member_count() == 2


def test_parse_v1_header():
    header_path = os.path.join(os.path.dirname(__file__), "..",
                               "variants/reference_project/headers/v1/telemetry_types.h")
    with open(header_path) as f:
        src = f.read()
    p = Parser()
    tc = p.parse(src)
    assert "TelemetryData_t" in tc.types
    assert "CommandMessage_t" in tc.types
    assert "SystemStatus_t" in tc.types
    # V1 TelemetryData_t: timestamp, speed, altitude, heading, latitude, longitude, status, payload = 8
    assert tc.types["TelemetryData_t"].member_count() == 8


def test_parse_v2_header():
    header_path = os.path.join(os.path.dirname(__file__), "..",
                               "variants/reference_project/headers/v2/telemetry_types.h")
    with open(header_path) as f:
        src = f.read()
    p = Parser()
    tc = p.parse(src)
    assert "TelemetryData_t" in tc.types
    # V2: timestamp, speed, altitude, heading, latitude, longitude, vertical_speed,
    #     status, signal_quality, payload, battery = 11
    assert tc.types["TelemetryData_t"].member_count() == 11


def test_parse_v3_header():
    header_path = os.path.join(os.path.dirname(__file__), "..",
                               "variants/reference_project/headers/v3/telemetry_types.h")
    with open(header_path) as f:
        src = f.read()
    p = Parser()
    tc = p.parse(src)
    assert "TelemetryData_t" in tc.types
    # V3: timestamp, ground_speed, altitude_msl, heading, latitude, longitude,
    #     vertical_speed, airspeed, op_status, signal_quality, satellite_count,
    #     mission_phase, sequence_number, payload, battery = 15
    assert tc.types["TelemetryData_t"].member_count() == 15


def test_bitfield():
    src = """
    typedef struct {
        uint32 flags : 4;
        uint32 reserved : 28;
    } BitStruct_t;
    """
    p = Parser()
    tc = p.parse(src)
    assert "BitStruct_t" in tc.types
    assert tc.types["BitStruct_t"].members[0].bitfield_width == 4
