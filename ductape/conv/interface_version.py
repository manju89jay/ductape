"""One header package at one version -> TypeContainer."""

import os
from ductape.conv.parser import Parser


class InterfaceVersion:
    """Parse one header directory at one version into a TypeContainer."""

    def __init__(self, base_dir, path, version_tag, additional_includes=None):
        self.base_dir = base_dir
        self.path = path
        self.version_tag = version_tag
        self.additional_includes = additional_includes or []
        self.container = None
        self.version_numbers = {}  # type_name -> version number

    def parse(self, version_macros):
        """Parse all .h files in the path directory.

        Args:
            version_macros: dict of type_name -> macro_name
        Returns:
            TypeContainer with all parsed types
        """
        header_dir = os.path.join(self.base_dir, self.path)
        parser = Parser()

        # Collect all header text
        all_text = ""
        for inc_dir in self.additional_includes:
            inc_path = os.path.join(self.base_dir, inc_dir)
            if os.path.isdir(inc_path):
                for fname in sorted(os.listdir(inc_path)):
                    if fname.endswith('.h'):
                        fpath = os.path.join(inc_path, fname)
                        with open(fpath) as f:
                            all_text += f.read() + "\n"

        if os.path.isdir(header_dir):
            for fname in sorted(os.listdir(header_dir)):
                if fname.endswith('.h'):
                    fpath = os.path.join(header_dir, fname)
                    with open(fpath) as f:
                        all_text += f.read() + "\n"

        self.container = parser.parse(all_text)

        # Extract version numbers from defines
        macro_to_type = {v: k for k, v in version_macros.items()}
        for define_name, define_val in self.container.defines.items():
            if define_name in macro_to_type:
                type_name = macro_to_type[define_name]
                if isinstance(define_val, int):
                    self.version_numbers[type_name] = define_val

        return self.container
