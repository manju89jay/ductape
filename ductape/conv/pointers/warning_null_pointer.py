"""Null-safe fallback with diagnostics."""


class WarningNullPointer:
    """Null-safe catch-all fallback that emits diagnostics."""

    def __init__(self, type_name="", field_name=""):
        self.type_name = type_name
        self.field_name = field_name
        self.warnings = []

    @property
    def is_struct(self):
        return False

    @property
    def is_array(self):
        return False

    @property
    def is_basic_type(self):
        return False

    @property
    def pass_able(self):
        return False

    @property
    def parent_source(self):
        return None

    @property
    def array_dimensions(self):
        return []

    def enter_struct(self, field_name, type_hint=None):
        self.warnings.append(f"Missing source for field '{field_name}' in {self.type_name}")
        return WarningNullPointer(self.type_name, field_name)

    def enter_array(self, dest=None):
        return WarningNullPointer(self.type_name, self.field_name)
