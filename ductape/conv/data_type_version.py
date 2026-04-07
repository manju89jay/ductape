"""One (type, version) tuple with struct layout."""
from __future__ import annotations

from dataclasses import dataclass, field

from ductape.conv.typecontainer import CType


@dataclass
class DataTypeVersion:
    """One version of one data type."""
    type_name: str
    version: int
    ctype: CType
    namespace: str = ""  # C++ namespace like TypeName_V_1

    def __post_init__(self) -> None:
        if not self.namespace:
            self.namespace = f"{self.type_name}_V_{self.version}"
