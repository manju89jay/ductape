"""Centralised diagnostic collector (WarningModule)."""
from __future__ import annotations

import sys
from typing import IO, Any


class WarningModule:
    """Collects and displays warnings with severity levels."""

    SEVERITY_NAMES: dict[int, str] = {0: "INFO", 1: "WARNING", 2: "ERROR"}
    SEVERITY_COLORS: dict[int, str] = {0: "\033[34m", 1: "\033[33m", 2: "\033[31m"}
    RESET: str = "\033[0m"

    def __init__(self, min_severity: int = 1, use_color: bool = True) -> None:
        self.min_severity: int = min_severity
        self.use_color: bool = use_color
        self.warnings: list[dict[str, Any]] = []

    def add(self, message: str, severity: int = 1, context: str = "") -> None:
        self.warnings.append({
            'message': message,
            'severity': severity,
            'context': context,
        })

    def display(self, file: IO[str] | None = None) -> None:
        file = file or sys.stderr
        for w in self.warnings:
            if w['severity'] >= self.min_severity:
                self._print_warning(w, file)

    def _print_warning(self, warning: dict[str, Any], file: IO[str]) -> None:
        sev = warning['severity']
        name = self.SEVERITY_NAMES.get(sev, "UNKNOWN")
        msg = warning['message']
        ctx = f" [{warning['context']}]" if warning['context'] else ""

        if self.use_color:
            color = self.SEVERITY_COLORS.get(sev, "")
            print(f"{color}[{name}]{self.RESET}{ctx} {msg}", file=file)
        else:
            print(f"[{name}]{ctx} {msg}", file=file)

    def has_errors(self) -> bool:
        return any(w['severity'] >= 2 for w in self.warnings)

    def count(self, min_severity: int = 0) -> int:
        return sum(1 for w in self.warnings if w['severity'] >= min_severity)
