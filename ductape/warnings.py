"""Centralised diagnostic collector (WarningModule)."""

import sys


class WarningModule:
    """Collects and displays warnings with severity levels."""

    SEVERITY_NAMES = {0: "INFO", 1: "WARNING", 2: "ERROR"}
    SEVERITY_COLORS = {0: "\033[34m", 1: "\033[33m", 2: "\033[31m"}
    RESET = "\033[0m"

    def __init__(self, min_severity=1, use_color=True):
        self.min_severity = min_severity
        self.use_color = use_color
        self.warnings = []

    def add(self, message, severity=1, context=""):
        self.warnings.append({
            'message': message,
            'severity': severity,
            'context': context,
        })

    def display(self, file=None):
        file = file or sys.stderr
        for w in self.warnings:
            if w['severity'] >= self.min_severity:
                self._print_warning(w, file)

    def _print_warning(self, warning, file):
        sev = warning['severity']
        name = self.SEVERITY_NAMES.get(sev, "UNKNOWN")
        msg = warning['message']
        ctx = f" [{warning['context']}]" if warning['context'] else ""

        if self.use_color:
            color = self.SEVERITY_COLORS.get(sev, "")
            print(f"{color}[{name}]{self.RESET}{ctx} {msg}", file=file)
        else:
            print(f"[{name}]{ctx} {msg}", file=file)

    def has_errors(self):
        return any(w['severity'] >= 2 for w in self.warnings)

    def count(self, min_severity=0):
        return sum(1 for w in self.warnings if w['severity'] >= min_severity)
