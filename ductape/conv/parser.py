"""Recursive-descent C parser -> TypeContainer."""

from ductape.conv.preprocessor import Preprocessor
from ductape.conv.expression_eval import ExpressionEvaluator
from ductape.conv.tokenizer import Tokenizer, TokenType
from ductape.conv.typecontainer import TypeContainer, CType, CTypeMember


class Parser:
    """Parse preprocessed C header text into a TypeContainer."""

    def __init__(self):
        self.warnings = []

    def parse(self, source_text):
        """Parse C header source text and return a TypeContainer."""
        pp = Preprocessor()
        clean_text = pp.process(source_text)

        self.expr_eval = ExpressionEvaluator()
        # Register defines
        for name, value in pp.defines.items():
            evaluated = self.expr_eval.evaluate(value)
            if evaluated is not None:
                self.expr_eval.add_symbol(name, evaluated)

        self.container = TypeContainer()
        # Add defines
        for name, value in pp.defines.items():
            evaluated = self.expr_eval.evaluate(value)
            self.container.add_define(name, evaluated if evaluated is not None else value)

        self.tokenizer = Tokenizer(clean_text)
        self._parse_top_level()
        return self.container

    def _parse_top_level(self):
        while not self.tokenizer.at_end():
            tok = self.tokenizer.peek()
            if tok.type == TokenType.Symbol and tok.value == 'typedef':
                self._parse_typedef()
            elif tok.type == TokenType.Symbol and tok.value == 'struct':
                self._parse_cpp_struct()
            elif tok.type == TokenType.Symbol and tok.value == 'union':
                self._parse_cpp_union()
            elif tok.type == TokenType.Symbol and tok.value == 'enum':
                self._parse_cpp_enum()
            elif tok.type == TokenType.Symbol and tok.value == '__attribute__':
                self._skip_attribute()
            elif tok.type == TokenType.Special and tok.value == ';':
                self.tokenizer.next()  # skip stray semicolons
            else:
                # Skip unknown tokens
                self.tokenizer.next()

    def _parse_typedef(self):
        self.tokenizer.expect(TokenType.Symbol, 'typedef')
        tok = self.tokenizer.peek()

        if tok.type == TokenType.Symbol and tok.value == 'struct':
            self._parse_typedef_struct()
        elif tok.type == TokenType.Symbol and tok.value == 'union':
            self._parse_typedef_union()
        elif tok.type == TokenType.Symbol and tok.value == 'enum':
            self._parse_typedef_enum()
        else:
            self._parse_typedef_alias()

    def _parse_typedef_struct(self):
        self.tokenizer.expect(TokenType.Symbol, 'struct')
        tok = self.tokenizer.peek()

        # Optional tag name
        tag_name = None
        if tok.type == TokenType.Symbol and tok.value != '{':
            next_tok = self.tokenizer.peek()
            # Check if it's a tag (followed by {)
            if next_tok.type == TokenType.Symbol:
                # peek ahead more
                saved = self.tokenizer._index
                tag_tok = self.tokenizer.next()
                if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '{':
                    tag_name = tag_tok.value
                else:
                    # Not a tag, restore
                    self.tokenizer._index = saved

        # Parse the struct body
        if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '{':
            members = self._parse_struct_body()
        else:
            # Forward declaration or other
            name = self.tokenizer.next().value
            self.tokenizer.match(TokenType.Special, ';')
            return

        # Skip __attribute__ between closing brace and typedef name
        if (self.tokenizer.peek().type == TokenType.Symbol and
                self.tokenizer.peek().value == '__attribute__'):
            self._skip_attribute()

        # Get the typedef name
        name_tok = self.tokenizer.expect(TokenType.Symbol)
        name = name_tok.value
        self.tokenizer.expect(TokenType.Special, ';')

        ctype = CType(
            name=name,
            is_struct=True,
            members=members,
        )
        self.container.add_type(name, ctype)

    def _parse_struct_body(self):
        self.tokenizer.expect(TokenType.Special, '{')
        members = []
        while not (self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '}'):
            if self.tokenizer.at_end():
                break
            member = self._parse_member()
            if member is not None:
                members.append(member)
        self.tokenizer.expect(TokenType.Special, '}')
        return members

    def _parse_member(self):
        tok = self.tokenizer.peek()

        # Handle nested struct
        if tok.type == TokenType.Symbol and tok.value == 'struct':
            return self._parse_nested_struct_member()

        # Handle nested union (treat members like struct)
        if tok.type == TokenType.Symbol and tok.value == 'union':
            return self._parse_nested_union_member()

        # Handle nested enum
        if tok.type == TokenType.Symbol and tok.value == 'enum':
            self.tokenizer.next()
            # Skip inline enum
            if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '{':
                self._skip_braces()
            name = self.tokenizer.next().value
            self.tokenizer.match(TokenType.Special, ';')
            return CTypeMember(name=name, type_name='int', is_enum=True)

        # Skip __attribute__((...))
        if tok.type == TokenType.Symbol and tok.value == '__attribute__':
            self._skip_attribute()

        # Skip qualifiers
        while (self.tokenizer.peek().type == TokenType.Symbol and
               self.tokenizer.peek().value in (
                   'const', 'volatile', 'unsigned', 'signed', 'long',
                   'static', 'restrict', 'register', 'inline',
                   '__restrict', '__inline', '__volatile',
               )):
            self.tokenizer.next()

        # Skip __attribute__ after qualifiers
        if (self.tokenizer.peek().type == TokenType.Symbol and
                self.tokenizer.peek().value == '__attribute__'):
            self._skip_attribute()

        # Read type name
        if self.tokenizer.peek().type != TokenType.Symbol:
            self.tokenizer.next()  # skip unexpected token
            return None

        type_name = self.tokenizer.next().value

        # Handle pointer
        while self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '*':
            self.tokenizer.next()
            type_name += '*'

        # Read member name
        if self.tokenizer.peek().type != TokenType.Symbol:
            # Could be anonymous or error
            self.tokenizer.match(TokenType.Special, ';')
            return None

        member_name = self.tokenizer.next().value

        # Array dimensions
        dimensions = []
        while self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '[':
            self.tokenizer.next()  # [
            dim_str = self._read_until(']')
            self.tokenizer.expect(TokenType.Special, ']')
            dim = self.expr_eval.evaluate(dim_str)
            if dim is not None:
                dimensions.append(dim)

        # Bitfield
        bitfield_width = None
        if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == ':':
            self.tokenizer.next()
            width_tok = self.tokenizer.next()
            bitfield_width = int(width_tok.value) if width_tok.value.isdigit() else None

        self.tokenizer.match(TokenType.Special, ';')

        is_basic = self.container.is_known_type(type_name) and self.container.get_type(type_name).is_basic_type
        is_struct_type = self.container.is_known_type(type_name) and self.container.get_type(type_name).is_struct
        # If not known yet but not basic, assume it might be a struct defined elsewhere
        if not self.container.is_known_type(type_name):
            is_basic = type_name in TypeContainer.BASIC_TYPES

        return CTypeMember(
            name=member_name,
            type_name=type_name,
            is_array=len(dimensions) > 0,
            dimensions=dimensions,
            is_struct=is_struct_type,
            is_basic_type=is_basic,
            bitfield_width=bitfield_width,
        )

    def _parse_nested_struct_member(self):
        self.tokenizer.expect(TokenType.Symbol, 'struct')

        # Optional tag
        tag = None
        if self.tokenizer.peek().type == TokenType.Symbol:
            saved = self.tokenizer._index
            tag_tok = self.tokenizer.next()
            if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '{':
                tag = tag_tok.value
            elif self.tokenizer.peek().type == TokenType.Symbol:
                # struct TypeName member_name;
                type_name = tag_tok.value
                member_name = self.tokenizer.next().value
                self.tokenizer.match(TokenType.Special, ';')
                return CTypeMember(name=member_name, type_name=type_name, is_struct=True)
            else:
                self.tokenizer._index = saved

        if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '{':
            members = self._parse_struct_body()
            if self.tokenizer.peek().type == TokenType.Symbol:
                member_name = self.tokenizer.next().value
                self.tokenizer.match(TokenType.Special, ';')
                return CTypeMember(name=member_name, type_name='struct', is_struct=True)
            self.tokenizer.match(TokenType.Special, ';')
            return None
        return None

    def _parse_typedef_enum(self):
        self.tokenizer.expect(TokenType.Symbol, 'enum')

        # Optional tag
        if self.tokenizer.peek().type == TokenType.Symbol:
            saved = self.tokenizer._index
            tag_tok = self.tokenizer.next()
            if not (self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '{'):
                self.tokenizer._index = saved

        enum_values = self._parse_enum_body()

        name_tok = self.tokenizer.expect(TokenType.Symbol)
        name = name_tok.value
        self.tokenizer.expect(TokenType.Special, ';')

        ctype = CType(
            name=name,
            is_enum=True,
            enum_values=enum_values,
        )
        self.container.add_type(name, ctype)

    def _parse_enum_body(self):
        self.tokenizer.expect(TokenType.Special, '{')
        values = []
        counter = 0
        while not (self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '}'):
            if self.tokenizer.at_end():
                break
            name_tok = self.tokenizer.expect(TokenType.Symbol)
            name = name_tok.value
            if self.tokenizer.match(TokenType.Special, '='):
                val_str = self._read_until(',', '}')
                val = self.expr_eval.evaluate(val_str)
                if val is not None:
                    counter = val
            values.append((name, counter))
            counter += 1
            self.tokenizer.match(TokenType.Special, ',')
        self.tokenizer.expect(TokenType.Special, '}')
        return values

    def _parse_typedef_alias(self):
        """Parse: typedef ExistingType NewAlias; or typedef Type ArrayAlias[N];"""
        # Read the type name (may be multi-word like "unsigned char")
        type_parts = [self.tokenizer.next().value]

        # Consume additional type qualifiers/parts
        while self.tokenizer.peek().type == TokenType.Symbol:
            # Peek two ahead to see if the next-next is ; or [ (meaning current next is alias)
            saved = self.tokenizer._index
            candidate = self.tokenizer.next()
            next_tok = self.tokenizer.peek()
            if next_tok.type == TokenType.Special and next_tok.value in (';', '[', '*'):
                # candidate is the alias name
                self.tokenizer._index = saved
                break
            elif next_tok.type == TokenType.EOF:
                self.tokenizer._index = saved
                break
            else:
                # It's part of the type
                self.tokenizer._index = saved
                type_parts.append(self.tokenizer.next().value)

        type_name = ' '.join(type_parts)

        # Handle pointer
        while self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '*':
            self.tokenizer.next()
            type_name += '*'

        alias_name = self.tokenizer.expect(TokenType.Symbol).value

        # Check for array dimensions
        dimensions = []
        while self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '[':
            self.tokenizer.next()
            dim_str = self._read_until(']')
            self.tokenizer.expect(TokenType.Special, ']')
            dim = self.expr_eval.evaluate(dim_str)
            if dim is not None:
                dimensions.append(dim)

        self.tokenizer.expect(TokenType.Special, ';')

        ctype = CType(
            name=alias_name,
            aliased_type=type_name,
            is_array=len(dimensions) > 0,
            dimensions=dimensions,
        )
        self.container.add_type(alias_name, ctype)

    def _parse_cpp_struct(self):
        """Parse: struct Name { ... };"""
        self.tokenizer.expect(TokenType.Symbol, 'struct')

        # Check for forward declaration
        name_tok = self.tokenizer.expect(TokenType.Symbol)
        name = name_tok.value

        if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == ';':
            # Forward declaration
            self.tokenizer.next()
            return

        if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '{':
            members = self._parse_struct_body()
            self.tokenizer.expect(TokenType.Special, ';')
            ctype = CType(name=name, is_struct=True, members=members)
            self.container.add_type(name, ctype)

    def _parse_cpp_enum(self):
        """Parse: enum Name { ... };"""
        self.tokenizer.expect(TokenType.Symbol, 'enum')
        name_tok = self.tokenizer.expect(TokenType.Symbol)
        name = name_tok.value

        if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '{':
            enum_values = self._parse_enum_body()
            self.tokenizer.expect(TokenType.Special, ';')
            ctype = CType(name=name, is_enum=True, enum_values=enum_values)
            self.container.add_type(name, ctype)

    def _parse_typedef_union(self):
        """Parse: typedef union { ... } Name;"""
        self.tokenizer.expect(TokenType.Symbol, 'union')
        tok = self.tokenizer.peek()

        # Optional tag name
        tag_name = None
        if tok.type == TokenType.Symbol and tok.value != '{':
            saved = self.tokenizer._index
            tag_tok = self.tokenizer.next()
            if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '{':
                tag_name = tag_tok.value
            else:
                self.tokenizer._index = saved

        if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '{':
            members = self._parse_struct_body()
        else:
            name = self.tokenizer.next().value
            self.tokenizer.match(TokenType.Special, ';')
            return

        name_tok = self.tokenizer.expect(TokenType.Symbol)
        name = name_tok.value
        self.tokenizer.expect(TokenType.Special, ';')

        ctype = CType(name=name, is_union=True, members=members)
        self.container.add_type(name, ctype)

    def _parse_cpp_union(self):
        """Parse: union Name { ... };"""
        self.tokenizer.expect(TokenType.Symbol, 'union')
        name_tok = self.tokenizer.expect(TokenType.Symbol)
        name = name_tok.value

        if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == ';':
            self.tokenizer.next()  # Forward declaration
            return

        if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '{':
            members = self._parse_struct_body()
            self.tokenizer.expect(TokenType.Special, ';')
            ctype = CType(name=name, is_union=True, members=members)
            self.container.add_type(name, ctype)

    def _parse_nested_union_member(self):
        """Parse a union member inside a struct."""
        self.tokenizer.expect(TokenType.Symbol, 'union')

        if self.tokenizer.peek().type == TokenType.Symbol:
            saved = self.tokenizer._index
            tag_tok = self.tokenizer.next()
            if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '{':
                pass  # Tagged inline union
            elif self.tokenizer.peek().type == TokenType.Symbol:
                # union TypeName member_name;
                type_name = tag_tok.value
                member_name = self.tokenizer.next().value
                self.tokenizer.match(TokenType.Special, ';')
                return CTypeMember(name=member_name, type_name=type_name, is_struct=True)
            else:
                self.tokenizer._index = saved

        if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '{':
            members = self._parse_struct_body()
            if self.tokenizer.peek().type == TokenType.Symbol:
                member_name = self.tokenizer.next().value
                self.tokenizer.match(TokenType.Special, ';')
                return CTypeMember(name=member_name, type_name='union', is_struct=True)
            self.tokenizer.match(TokenType.Special, ';')
            return None
        return None

    def _skip_attribute(self):
        """Skip __attribute__((...)) declarations."""
        if self.tokenizer.peek().type == TokenType.Symbol and self.tokenizer.peek().value == '__attribute__':
            self.tokenizer.next()  # __attribute__
        # Skip balanced parentheses
        if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '(':
            depth = 0
            while not self.tokenizer.at_end():
                tok = self.tokenizer.next()
                if tok.type == TokenType.Special and tok.value == '(':
                    depth += 1
                elif tok.type == TokenType.Special and tok.value == ')':
                    depth -= 1
                    if depth == 0:
                        break

    def _read_until(self, *stop_chars):
        """Read tokens until a stop character, returning concatenated text."""
        parts = []
        while True:
            tok = self.tokenizer.peek()
            if tok.type == TokenType.EOF:
                break
            if tok.type == TokenType.Special and tok.value in stop_chars:
                break
            parts.append(self.tokenizer.next().value)
        return ' '.join(parts)

    def _skip_braces(self):
        """Skip a brace-enclosed block."""
        depth = 0
        if self.tokenizer.peek().type == TokenType.Special and self.tokenizer.peek().value == '{':
            self.tokenizer.next()
            depth = 1
        while depth > 0 and not self.tokenizer.at_end():
            tok = self.tokenizer.next()
            if tok.type == TokenType.Special and tok.value == '{':
                depth += 1
            elif tok.type == TokenType.Special and tok.value == '}':
                depth -= 1
