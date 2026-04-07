"""AST-like model: types, defines, namespaces."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field


@dataclass
class CType:
    name: str
    is_struct: bool = False
    is_union: bool = False
    is_enum: bool = False
    is_basic_type: bool = False
    is_array: bool = False
    dimensions: list[int] = field(default_factory=list)
    members: list[CTypeMember] = field(default_factory=list)
    enum_values: list[tuple[str, int]] = field(default_factory=list)
    aliased_type: str | None = None
    bitfield_width: int | None = None

    def member_count(self) -> int:
        return len(self.members)


@dataclass
class CTypeMember:
    name: str
    type_name: str
    is_array: bool = False
    dimensions: list[int] = field(default_factory=list)
    is_struct: bool = False
    is_enum: bool = False
    is_basic_type: bool = False
    bitfield_width: int | None = None


class TypeContainer:
    """Container for parsed C types, defines, and namespaces."""

    # Standard C/platform basic types
    BASIC_TYPES = [
        'void', 'char', 'short', 'int', 'long', 'float', 'double',
        'unsigned', 'signed',
        'uint8', 'sint8', 'uint16', 'sint16', 'uint32', 'sint32',
        'uint64', 'sint64', 'float32', 'float64', 'boolean',
        'uint8_t', 'int8_t', 'uint16_t', 'int16_t', 'uint32_t', 'int32_t',
        'uint64_t', 'int64_t', 'size_t', 'bool',
    ]

    def __init__(self) -> None:
        self.basictypes: OrderedDict[str, CType] = OrderedDict()
        self.types: OrderedDict[str, CType] = OrderedDict()
        self.defines: OrderedDict[str, int] = OrderedDict()
        self.namespaces: OrderedDict[str, TypeContainer] = OrderedDict()
        self._init_basic_types()

    def _init_basic_types(self) -> None:
        for t in self.BASIC_TYPES:
            self.basictypes[t] = CType(name=t, is_basic_type=True)

    def add_type(self, name: str, ctype: CType) -> None:
        self.types[name] = ctype

    def add_define(self, name: str, value: int) -> None:
        self.defines[name] = value

    def get_type(self, name: str) -> CType | None:
        if name in self.types:
            return self.types[name]
        if name in self.basictypes:
            return self.basictypes[name]
        return None

    def is_known_type(self, name: str) -> bool:
        return name in self.types or name in self.basictypes

    def add_namespace(self, name: str, container: TypeContainer) -> None:
        self.namespaces[name] = container
