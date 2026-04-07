"""Centralized exception hierarchy for ductape."""


class DuctapeError(Exception):
    """Base exception for all ductape errors."""
    pass


class ConfigError(DuctapeError):
    """Invalid or missing configuration."""
    pass


class ParseError(DuctapeError):
    """Failed to parse a schema file (header, proto, JSON schema)."""
    pass


class EmitterError(DuctapeError):
    """Failed during code emission."""
    pass


class VersionConflictError(DuctapeError):
    """Same version number has structurally different layouts (FR-14)."""
    pass


class AmbiguousMemberError(DuctapeError):
    """Fuzzy lookup matched multiple struct member candidates."""
    pass
