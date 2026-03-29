"""JSON Schema parser frontend (FR-24).

Parses JSON Schema files (draft-07+) into TypeContainer.
Maps: object -> struct, array -> array, $ref -> type reference, enum -> enum.
"""

import os
import json
from collections import OrderedDict
from ductape.frontends.frontend_base import ParserFrontend, register_frontend
from ductape.conv.typecontainer import TypeContainer, CType, CTypeMember

# JSON Schema type -> C-equivalent type mapping
JSON_TYPE_MAP = {
    'integer': 'sint32',
    'number': 'float64',
    'boolean': 'boolean',
    'string': 'uint8',  # Mapped as char array
}

DEFAULT_ARRAY_SIZE = 64
DEFAULT_STRING_SIZE = 256


@register_frontend
class JsonSchemaFrontend(ParserFrontend):
    """Parser frontend for JSON Schema files."""

    format_id = "json_schema"

    def parse(self, schema_path, config):
        """Parse JSON Schema files and return a TypeContainer.

        Args:
            schema_path: Path to a .json schema file or directory
            config: Full config dict
        Returns:
            Populated TypeContainer
        """
        base_dir = config.get('_config_dir', '.')
        path = schema_path
        if not os.path.isabs(path):
            path = os.path.join(base_dir, path)

        container = TypeContainer()
        self._definitions = {}  # Cache for $ref resolution

        if os.path.isdir(path):
            for fname in sorted(os.listdir(path)):
                if fname.endswith('.json'):
                    fpath = os.path.join(path, fname)
                    with open(fpath) as f:
                        schema = json.load(f)
                    self._parse_schema(schema, container, fname)
        elif os.path.isfile(path):
            with open(path) as f:
                schema = json.load(f)
            self._parse_schema(schema, container, os.path.basename(path))

        return container

    def file_extensions(self):
        return ['.json']

    def _parse_schema(self, schema, container, source_name):
        """Parse a single JSON Schema document."""
        if not isinstance(schema, dict):
            return

        # Cache definitions/$defs for $ref resolution
        for key in ('definitions', '$defs'):
            if key in schema:
                for def_name, def_schema in schema[key].items():
                    self._definitions[def_name] = def_schema
                    self._parse_type(def_name, def_schema, container)

        # Parse the root schema if it's an object type
        title = schema.get('title', source_name.replace('.json', ''))
        schema_type = schema.get('type', '')

        if schema_type == 'object' or 'properties' in schema:
            self._parse_type(title, schema, container)
        elif 'enum' in schema:
            self._parse_enum_type(title, schema, container)

    def _parse_type(self, name, schema, container):
        """Parse a schema object into a CType."""
        schema_type = schema.get('type', '')

        if schema_type == 'object' or 'properties' in schema:
            members = self._parse_object_properties(schema, container)
            ctype = CType(name=name, is_struct=True, members=members)
            container.add_type(name, ctype)
        elif 'enum' in schema:
            self._parse_enum_type(name, schema, container)

    def _parse_object_properties(self, schema, container):
        """Parse properties of an object schema into CTypeMembers."""
        members = []
        properties = schema.get('properties', {})

        for prop_name, prop_schema in properties.items():
            member = self._parse_property(prop_name, prop_schema, container)
            if member:
                members.append(member)

        return members

    def _parse_property(self, name, schema, container):
        """Parse a single property schema into a CTypeMember."""
        # Resolve $ref
        if '$ref' in schema:
            ref = schema['$ref']
            ref_name = ref.split('/')[-1]
            # Resolve from definitions cache
            if ref_name in self._definitions:
                resolved = self._definitions[ref_name]
                ref_type = resolved.get('type', 'object')
                if ref_type == 'object' or 'properties' in resolved:
                    # Ensure the referenced type is in the container
                    self._parse_type(ref_name, resolved, container)
                    return CTypeMember(
                        name=name, type_name=ref_name, is_struct=True,
                    )
            return CTypeMember(
                name=name, type_name=ref_name,
                is_struct=True,
            )

        schema_type = schema.get('type', '')

        # Handle enum
        if 'enum' in schema:
            enum_name = f"{name}_enum_t"
            values = [(str(v), i) for i, v in enumerate(schema['enum'])]
            ctype = CType(name=enum_name, is_enum=True, enum_values=values)
            container.add_type(enum_name, ctype)
            return CTypeMember(
                name=name, type_name='uint32', is_basic_type=True, is_enum=True,
            )

        # Handle array
        if schema_type == 'array':
            items = schema.get('items', {})
            max_items = schema.get('maxItems', DEFAULT_ARRAY_SIZE)
            item_type = items.get('type', 'sint32')
            mapped = JSON_TYPE_MAP.get(item_type, item_type)

            if item_type == 'object' or 'properties' in items:
                item_name = items.get('title', f"{name}_item_t")
                self._parse_type(item_name, items, container)
                return CTypeMember(
                    name=name, type_name=item_name, is_array=True,
                    dimensions=[max_items], is_struct=True,
                )

            is_basic = mapped in TypeContainer.BASIC_TYPES
            return CTypeMember(
                name=name, type_name=mapped, is_array=True,
                dimensions=[max_items], is_basic_type=is_basic,
            )

        # Handle nested object
        if schema_type == 'object' or 'properties' in schema:
            nested_name = schema.get('title', f"{name}_t")
            self._parse_type(nested_name, schema, container)
            return CTypeMember(
                name=name, type_name=nested_name, is_struct=True,
            )

        # Handle basic types
        if schema_type == 'string':
            max_len = schema.get('maxLength', DEFAULT_STRING_SIZE)
            return CTypeMember(
                name=name, type_name='uint8', is_array=True,
                dimensions=[max_len], is_basic_type=True,
            )

        mapped = JSON_TYPE_MAP.get(schema_type, 'uint8')
        return CTypeMember(
            name=name, type_name=mapped,
            is_basic_type=mapped in TypeContainer.BASIC_TYPES,
        )
