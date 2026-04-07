"""Abstract ParserFrontend interface (FR-22).

Every parser frontend implements this contract. New schema formats are added
by subclassing ParserFrontend and implementing `parse()`, without modifying
the core engine or any existing frontend.
"""

from abc import ABC, abstractmethod
from ductape.conv.typecontainer import TypeContainer
from ductape.exceptions import ParseError


class ParserFrontend(ABC):
    """Interface that all parser frontends implement."""

    # Identifier used in config.yaml: format: "c_header" | "protobuf" | ...
    format_id: str = ""

    @abstractmethod
    def parse(self, schema_path, config):
        """Parse a schema file/directory and return a populated TypeContainer.

        The TypeContainer must contain:
        - types: OrderedDict of parsed data types (structs/messages/objects)
        - defines: OrderedDict of version constants (if applicable)
        - Each type's members with: name, base_type, is_array, dimensions

        Args:
            schema_path: Path to the schema file or directory
            config: The full loaded config dict

        Returns:
            Populated TypeContainer
        """
        raise NotImplementedError

    @abstractmethod
    def file_extensions(self):
        """Return list of file extensions this frontend handles (e.g. ['.h'])."""
        raise NotImplementedError


# Registry of available frontends
_FRONTEND_REGISTRY = {}


def register_frontend(frontend_class):
    """Register a parser frontend class."""
    _FRONTEND_REGISTRY[frontend_class.format_id] = frontend_class
    return frontend_class


def get_frontend(format_id):
    """Look up a registered frontend by format_id.

    Args:
        format_id: string like "c_header", "protobuf", "json_schema"
    Returns:
        An instance of the matching ParserFrontend subclass
    Raises:
        ValueError if format_id is not registered
    """
    if format_id not in _FRONTEND_REGISTRY:
        available = ', '.join(sorted(_FRONTEND_REGISTRY.keys()))
        raise ParseError(
            f"Unknown parser frontend '{format_id}'. "
            f"Available: {available}"
        )
    return _FRONTEND_REGISTRY[format_id]()


def list_frontends():
    """Return dict of format_id -> frontend class for all registered frontends."""
    return dict(_FRONTEND_REGISTRY)
