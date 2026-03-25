"""Tests for pointer abstractions."""

import pytest
from ductape.conv.typecontainer import CType, CTypeMember
from ductape.conv.pointers.struct_pointer import StructPointer, AmbiguousMemberError
from ductape.conv.pointers.value_pointer import ValuePointer
from ductape.conv.pointers.warning_null_pointer import WarningNullPointer
from ductape.conv.value_container import ValueContainer


def _make_struct():
    return CType(
        name="TestStruct",
        is_struct=True,
        members=[
            CTypeMember(name="x", type_name="uint32", is_basic_type=True),
            CTypeMember(name="y", type_name="float32", is_basic_type=True),
            CTypeMember(name="data", type_name="uint8", is_array=True, dimensions=[32], is_basic_type=True),
        ],
    )


def test_exact_match():
    sp = StructPointer(_make_struct(), "Test_V_1")
    result = sp.enter_struct("x")
    assert result is not None
    assert result.ctype.name == "uint32"


def test_exact_match_not_found():
    sp = StructPointer(_make_struct(), "Test_V_1")
    result = sp.enter_struct("nonexistent")
    assert result is None


def test_fuzzy_match_with_suffix():
    ct = CType(
        name="Test",
        is_struct=True,
        members=[
            CTypeMember(name="speed_t", type_name="float32", is_basic_type=True),
        ],
    )
    sp = StructPointer(ct, "Test_V_1")
    result = sp.enter_struct("speed")
    assert result is not None


def test_ambiguity_error():
    ct = CType(
        name="Test",
        is_struct=True,
        members=[
            CTypeMember(name="speed_t", type_name="float32", is_basic_type=True),
            CTypeMember(name="speed_T", type_name="float32", is_basic_type=True),
        ],
    )
    sp = StructPointer(ct, "Test_V_1")
    with pytest.raises(AmbiguousMemberError):
        sp.enter_struct("speed")


def test_value_pointer():
    vp = ValuePointer({"x": "42", "nested": {"a": "1"}})
    child = vp.enter_struct("x")
    assert child is not None
    assert child.get_value() == "42"

    nested = vp.enter_struct("nested")
    assert nested.is_struct
    a = nested.enter_struct("a")
    assert a.get_value() == "1"


def test_warning_null_pointer():
    wnp = WarningNullPointer("Test", "field")
    result = wnp.enter_struct("x")
    assert isinstance(result, WarningNullPointer)
    assert len(wnp.warnings) == 1


def test_value_container_tree():
    vc = ValueContainer({"battery.voltage": "0.0", "battery.current": "0.0", "speed": "0"})
    assert vc.has("battery")
    assert vc.has("speed")
    bat = vc.get("battery")
    assert bat == {"voltage": "0.0", "current": "0.0"}


def test_struct_pointer_array():
    sp = StructPointer(_make_struct(), "Test_V_1")
    data = sp.enter_struct("data")
    assert data is not None
    assert data.ctype.is_array
    assert data.ctype.dimensions == [32]
