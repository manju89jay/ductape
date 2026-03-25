"""Default/override value pointer."""


class ValuePointer:
    """Wraps a tree of explicit default/override values."""

    def __init__(self, values=None, parent=None):
        self.values = values or {}
        self._parent = parent

    @property
    def is_struct(self):
        return isinstance(self.values, dict)

    @property
    def is_array(self):
        return False

    @property
    def is_basic_type(self):
        return not isinstance(self.values, dict)

    @property
    def pass_able(self):
        return False

    @property
    def parent_source(self):
        return self._parent

    @property
    def array_dimensions(self):
        return []

    def enter_struct(self, field_name, type_hint=None):
        if isinstance(self.values, dict) and field_name in self.values:
            val = self.values[field_name]
            return ValuePointer(val, parent=self)
        return None

    def enter_array(self, dest=None):
        return None

    def get_value(self):
        if not isinstance(self.values, dict):
            return self.values
        return None
