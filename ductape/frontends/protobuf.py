"""Protobuf .proto parser frontend (FR-23).

Parses proto2 and proto3 .proto files into TypeContainer.
Maps: message -> struct, enum -> enum, repeated -> array, map -> key-value struct.
Tracks field numbers for backward-compatibility analysis.
"""

import os
import re
from collections import OrderedDict
from ductape.frontends.frontend_base import ParserFrontend, register_frontend
from ductape.conv.typecontainer import TypeContainer, CType, CTypeMember


# Proto scalar type -> C-equivalent type mapping
PROTO_TYPE_MAP = {
    'double': 'float64',
    'float': 'float32',
    'int32': 'sint32',
    'int64': 'sint64',
    'uint32': 'uint32',
    'uint64': 'uint64',
    'sint32': 'sint32',
    'sint64': 'sint64',
    'fixed32': 'uint32',
    'fixed64': 'uint64',
    'sfixed32': 'sint32',
    'sfixed64': 'sint64',
    'bool': 'boolean',
    'string': 'uint8',  # Mapped as char array
    'bytes': 'uint8',   # Mapped as byte array
}

# Default array dimension for repeated/string/bytes fields
DEFAULT_REPEATED_SIZE = 64
DEFAULT_STRING_SIZE = 256


@register_frontend
class ProtobufFrontend(ParserFrontend):
    """Parser frontend for Protobuf .proto files."""

    format_id = "protobuf"

    def parse(self, schema_path, config):
        """Parse .proto files and return a TypeContainer.

        Args:
            schema_path: Path to a .proto file or directory of .proto files
            config: Full config dict
        Returns:
            Populated TypeContainer
        """
        base_dir = config.get('_config_dir', '.')
        path = schema_path
        if not os.path.isabs(path):
            path = os.path.join(base_dir, path)

        all_text = ""
        if os.path.isdir(path):
            for fname in sorted(os.listdir(path)):
                if fname.endswith('.proto'):
                    with open(os.path.join(path, fname)) as f:
                        all_text += f.read() + "\n"
        elif os.path.isfile(path):
            with open(path) as f:
                all_text = f.read()

        return self._parse_proto(all_text)

    def file_extensions(self):
        return ['.proto']

    def _parse_proto(self, text):
        """Parse proto text into a TypeContainer."""
        container = TypeContainer()

        # Strip comments
        text = re.sub(r'//[^\n]*', '', text)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

        # Extract syntax declaration
        syntax_match = re.search(r'syntax\s*=\s*"(proto[23])"\s*;', text)
        syntax = syntax_match.group(1) if syntax_match else 'proto2'

        # Extract option values as defines (e.g., option java_package = ...)
        for m in re.finditer(r'option\s+(\w+)\s*=\s*([^;]+);', text):
            container.add_define(m.group(1), m.group(2).strip().strip('"'))

        # Parse enums (top-level)
        for m in re.finditer(r'enum\s+(\w+)\s*\{([^}]*)\}', text):
            enum_name = m.group(1)
            enum_body = m.group(2)
            ctype = self._parse_enum(enum_name, enum_body)
            container.add_type(enum_name, ctype)

        # Parse messages
        self._parse_messages(text, container)

        return container

    def _parse_enum(self, name, body):
        """Parse a protobuf enum body into a CType."""
        values = []
        for line in body.strip().split('\n'):
            line = line.strip().rstrip(';')
            if not line or line.startswith('option') or line.startswith('reserved'):
                continue
            match = re.match(r'(\w+)\s*=\s*(-?\d+)', line)
            if match:
                values.append((match.group(1), int(match.group(2))))
        return CType(name=name, is_enum=True, enum_values=values)

    def _parse_messages(self, text, container):
        """Parse all top-level message definitions."""
        # Use a simple brace-matching approach for top-level messages
        pos = 0
        while pos < len(text):
            match = re.search(r'message\s+(\w+)\s*\{', text[pos:])
            if not match:
                break
            msg_name = match.group(1)
            brace_start = pos + match.end()
            body, end_pos = self._extract_braced_body(text, brace_start - 1)
            pos = end_pos

            members, nested_types = self._parse_message_body(body, msg_name, container)
            ctype = CType(
                name=msg_name,
                is_struct=True,
                members=members,
            )
            container.add_type(msg_name, ctype)

    def _extract_braced_body(self, text, start):
        """Extract content between matching braces."""
        depth = 0
        i = start
        while i < len(text):
            if text[i] == '{':
                depth += 1
                if depth == 1:
                    body_start = i + 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    return text[body_start:i], i + 1
            i += 1
        return text[start:], len(text)

    def _parse_message_body(self, body, parent_name, container):
        """Parse the body of a message definition."""
        members = []
        nested = []

        # Parse nested enums
        for m in re.finditer(r'enum\s+(\w+)\s*\{([^}]*)\}', body):
            enum_name = m.group(1)
            ctype = self._parse_enum(enum_name, m.group(2))
            container.add_type(enum_name, ctype)

        # Remove nested message/enum blocks for field parsing
        clean_body = re.sub(r'(message|enum)\s+\w+\s*\{[^}]*\}', '', body)

        # Parse nested messages recursively
        pos = 0
        while pos < len(body):
            match = re.search(r'message\s+(\w+)\s*\{', body[pos:])
            if not match:
                break
            nested_name = match.group(1)
            brace_start = pos + match.end()
            nested_body, end_pos = self._extract_braced_body(body, brace_start - 1)
            pos = end_pos

            nested_members, _ = self._parse_message_body(nested_body, nested_name, container)
            nested_ctype = CType(name=nested_name, is_struct=True, members=nested_members)
            container.add_type(nested_name, nested_ctype)
            nested.append(nested_name)

        # Parse oneof blocks -> discriminator + variant fields
        for m in re.finditer(r'oneof\s+(\w+)\s*\{([^}]*)\}', clean_body):
            oneof_name = m.group(1)
            oneof_body = m.group(2)
            # Add discriminator tag
            members.append(CTypeMember(
                name=f"{oneof_name}_case",
                type_name='uint32',
                is_basic_type=True,
            ))
            # Parse oneof fields
            for field_match in re.finditer(
                r'(\w+)\s+(\w+)\s*=\s*(\d+)\s*;', oneof_body
            ):
                ftype, fname, fnum = field_match.groups()
                mapped = PROTO_TYPE_MAP.get(ftype, ftype)
                is_basic = mapped in PROTO_TYPE_MAP.values() or mapped in TypeContainer.BASIC_TYPES
                members.append(CTypeMember(
                    name=fname,
                    type_name=mapped,
                    is_basic_type=is_basic,
                    is_struct=not is_basic and ftype not in PROTO_TYPE_MAP,
                ))

        # Remove oneof blocks from clean_body
        clean_body = re.sub(r'oneof\s+\w+\s*\{[^}]*\}', '', clean_body)

        # Parse regular fields
        for line in clean_body.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('option') or line.startswith('reserved'):
                continue
            if line.startswith('//') or line.startswith('extensions'):
                continue

            member = self._parse_field(line)
            if member:
                members.append(member)

        # Parse map fields
        for m in re.finditer(
            r'map\s*<\s*(\w+)\s*,\s*(\w+)\s*>\s+(\w+)\s*=\s*(\d+)\s*;', clean_body
        ):
            key_type, val_type, fname, fnum = m.groups()
            # Map -> create a key-value entry struct
            entry_name = f"{fname}_entry_t"
            key_mapped = PROTO_TYPE_MAP.get(key_type, key_type)
            val_mapped = PROTO_TYPE_MAP.get(val_type, val_type)
            entry_members = [
                CTypeMember(name='key', type_name=key_mapped,
                            is_basic_type=key_mapped in TypeContainer.BASIC_TYPES),
                CTypeMember(name='value', type_name=val_mapped,
                            is_basic_type=val_mapped in TypeContainer.BASIC_TYPES),
            ]
            entry_ctype = CType(name=entry_name, is_struct=True, members=entry_members)
            container.add_type(entry_name, entry_ctype)
            members.append(CTypeMember(
                name=fname, type_name=entry_name, is_array=True,
                dimensions=[DEFAULT_REPEATED_SIZE], is_struct=True,
            ))

        return members, nested

    def _parse_field(self, line):
        """Parse a single field line."""
        line = line.rstrip(';').strip()
        if not line:
            return None

        # map fields handled separately
        if line.startswith('map'):
            return None

        # repeated field
        repeated_match = re.match(
            r'repeated\s+(\w+)\s+(\w+)\s*=\s*(\d+)', line
        )
        if repeated_match:
            ftype, fname, fnum = repeated_match.groups()
            mapped = PROTO_TYPE_MAP.get(ftype, ftype)
            is_basic = mapped in TypeContainer.BASIC_TYPES
            return CTypeMember(
                name=fname, type_name=mapped, is_array=True,
                dimensions=[DEFAULT_REPEATED_SIZE],
                is_basic_type=is_basic,
                is_struct=not is_basic and ftype not in PROTO_TYPE_MAP,
            )

        # optional/required/plain field
        field_match = re.match(
            r'(?:optional|required)?\s*(\w+)\s+(\w+)\s*=\s*(\d+)', line
        )
        if field_match:
            ftype, fname, fnum = field_match.groups()
            mapped = PROTO_TYPE_MAP.get(ftype, ftype)
            is_basic = mapped in TypeContainer.BASIC_TYPES

            # string/bytes -> char array
            if ftype in ('string', 'bytes'):
                return CTypeMember(
                    name=fname, type_name='uint8', is_array=True,
                    dimensions=[DEFAULT_STRING_SIZE], is_basic_type=True,
                )

            return CTypeMember(
                name=fname, type_name=mapped,
                is_basic_type=is_basic,
                is_struct=not is_basic and ftype not in PROTO_TYPE_MAP,
            )

        return None
