"""Low-level file writer with indentation tracking."""
from __future__ import annotations

import os


class CodeWriter:
    """C++ file writer with indent tracking."""

    def __init__(self, indent_str: str = "  ") -> None:
        self.indent_str: str = indent_str
        self.indent_level: int = 0
        self.lines: list[str] = []

    def line(self, text: str = "") -> None:
        if text:
            self.lines.append(self.indent_str * self.indent_level + text)
        else:
            self.lines.append("")

    def indent(self) -> None:
        self.indent_level += 1

    def dedent(self) -> None:
        self.indent_level = max(0, self.indent_level - 1)

    def block_open(self, text: str = "") -> None:
        if text:
            self.line(text)
        self.line("{")
        self.indent()

    def block_close(self, suffix: str = "") -> None:
        self.dedent()
        self.line("}" + suffix)

    def get_content(self) -> str:
        return '\n'.join(self.lines) + '\n'

    def write_to(self, filepath: str) -> None:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(self.get_content())
