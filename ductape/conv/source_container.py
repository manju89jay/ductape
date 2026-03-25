"""Multi-source pointer manager for tree-walking."""


class SourceContainer:
    """Manages an ordered, priority-ranked list of pointers for one destination struct node."""

    def __init__(self, pointers=None):
        self.pointers = pointers or []
        self.used = set()
        self.child_used = set()

    def add_pointer(self, pointer, priority=None):
        if priority is not None:
            self.pointers.insert(priority, pointer)
        else:
            self.pointers.append(pointer)

    def enter_struct(self, field_name, type_hint=None):
        """Try each pointer in priority order."""
        for i, ptr in enumerate(self.pointers):
            result = ptr.enter_struct(field_name, type_hint)
            if result is not None:
                self.used.add(i)
                return result
        return None

    def get_best_source(self, field_name, type_hint=None):
        """Get the highest-priority source that has this field."""
        for i, ptr in enumerate(self.pointers):
            result = ptr.enter_struct(field_name, type_hint)
            if result is not None:
                self.used.add(i)
                return ptr, result
        return None, None
