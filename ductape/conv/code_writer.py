"""Low-level file writer with indentation tracking."""

import os


class CodeWriter:
    """C++ file writer with indent tracking."""

    def __init__(self, indent_str="  "):
        self.indent_str = indent_str
        self.indent_level = 0
        self.lines = []

    def line(self, text=""):
        if text:
            self.lines.append(self.indent_str * self.indent_level + text)
        else:
            self.lines.append("")

    def indent(self):
        self.indent_level += 1

    def dedent(self):
        self.indent_level = max(0, self.indent_level - 1)

    def block_open(self, text=""):
        if text:
            self.line(text)
        self.line("{")
        self.indent()

    def block_close(self, suffix=""):
        self.dedent()
        self.line("}" + suffix)

    def get_content(self):
        return '\n'.join(self.lines) + '\n'

    def write_to(self, filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(self.get_content())
