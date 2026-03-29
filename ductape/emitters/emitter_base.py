"""Abstract CodeEmitter interface (FR-25).

Every code emitter implements this contract. New output languages are added
by subclassing CodeEmitter and implementing the emit methods, without modifying
the core engine or any existing emitter.
"""

from abc import ABC, abstractmethod


class CodeEmitter(ABC):
    """Interface that all code emitters implement."""

    # Identifier used in config.yaml: emitter: "cpp" | "python" | "rust" | ...
    emitter_id: str = ""

    @abstractmethod
    def emit_type_header(self, data_type, output_dir, registry=None):
        """Emit versioned type definitions for one data type.

        Args:
            data_type: DataType instance with all versions and generic
            output_dir: Root output directory
            registry: TypeRegistry for resolving dependent types
        """
        raise NotImplementedError

    @abstractmethod
    def emit_converter(self, data_type, config, output_dir, warning_module=None):
        """Emit converter code for one data type.

        Args:
            data_type: DataType instance
            config: Full config dict
            output_dir: Root output directory
            warning_module: Optional WarningModule for missing-field warnings
        """
        raise NotImplementedError

    @abstractmethod
    def emit_factory(self, data_types, output_dir):
        """Emit the factory/registry that lists all generated converters.

        Args:
            data_types: dict of type_name -> DataType
            output_dir: Root output directory
        """
        raise NotImplementedError

    def emit_platform_types(self, config, output_dir):
        """Copy or emit platform type definitions. Optional override.

        Args:
            config: Full config dict
            output_dir: Root output directory
        """
        pass


# Registry of available emitters
_EMITTER_REGISTRY = {}


def register_emitter(emitter_class):
    """Register a code emitter class."""
    _EMITTER_REGISTRY[emitter_class.emitter_id] = emitter_class
    return emitter_class


def get_emitter(emitter_id):
    """Look up a registered emitter by emitter_id.

    Args:
        emitter_id: string like "cpp", "python", "rust"
    Returns:
        An instance of the matching CodeEmitter subclass
    Raises:
        ValueError if emitter_id is not registered
    """
    if emitter_id not in _EMITTER_REGISTRY:
        available = ', '.join(sorted(_EMITTER_REGISTRY.keys()))
        raise ValueError(
            f"Unknown code emitter '{emitter_id}'. "
            f"Available: {available}"
        )
    return _EMITTER_REGISTRY[emitter_id]()


def list_emitters():
    """Return dict of emitter_id -> emitter class for all registered emitters."""
    return dict(_EMITTER_REGISTRY)
