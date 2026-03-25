"""Default / override value holder."""


class ValueContainer:
    """Holds a tree of default/override values parsed from config."""

    def __init__(self, defaults_dict=None):
        self.tree = {}
        if defaults_dict:
            self._build_tree(defaults_dict)

    def _build_tree(self, flat_dict):
        """Convert dot-separated keys to nested dict."""
        for key, value in flat_dict.items():
            parts = key.split('.')
            node = self.tree
            for part in parts[:-1]:
                if part not in node:
                    node[part] = {}
                node = node[part]
            node[parts[-1]] = value

    def get(self, field_name):
        return self.tree.get(field_name)

    def has(self, field_name):
        return field_name in self.tree
