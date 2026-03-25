"""Lexer: classifies text into typed tokens."""

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    Symbol = auto()
    Integer = auto()
    Float = auto()
    String = auto()
    Special = auto()
    Operator = auto()
    EOF = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    line: int = 0

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r})"


SPECIAL_CHARS = set('{}[];*(),:')
OPERATOR_CHARS = set('+-/^')  # * is in Special


class Tokenizer:
    """Tokenize preprocessed C source text."""

    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.line = 1
        self.tokens = []
        self._tokenize()
        self._index = 0

    def _tokenize(self):
        while self.pos < len(self.text):
            ch = self.text[self.pos]

            if ch == '\n':
                self.line += 1
                self.pos += 1
                continue
            if ch.isspace():
                self.pos += 1
                continue

            # String literal
            if ch in ('"', "'"):
                self._read_string(ch)
                continue

            # Number
            if ch.isdigit() or (ch == '.' and self.pos + 1 < len(self.text) and self.text[self.pos + 1].isdigit()):
                self._read_number()
                continue

            # Symbol/keyword
            if ch.isalpha() or ch == '_':
                self._read_symbol()
                continue

            # Special characters
            if ch in SPECIAL_CHARS:
                self.tokens.append(Token(TokenType.Special, ch, self.line))
                self.pos += 1
                continue

            # Operators
            if ch in OPERATOR_CHARS:
                self.tokens.append(Token(TokenType.Operator, ch, self.line))
                self.pos += 1
                continue

            # Assignment
            if ch == '=':
                self.tokens.append(Token(TokenType.Special, '=', self.line))
                self.pos += 1
                continue

            # Skip unknown characters
            self.pos += 1

        self.tokens.append(Token(TokenType.EOF, '', self.line))

    def _read_string(self, quote):
        start = self.pos
        self.pos += 1  # skip opening quote
        while self.pos < len(self.text) and self.text[self.pos] != quote:
            if self.text[self.pos] == '\\':
                self.pos += 1  # skip escape
            if self.text[self.pos] == '\n':
                self.line += 1
            self.pos += 1
        self.pos += 1  # skip closing quote
        self.tokens.append(Token(TokenType.String, self.text[start:self.pos], self.line))

    def _read_number(self):
        start = self.pos
        is_float = False
        # Handle hex
        if self.text[self.pos] == '0' and self.pos + 1 < len(self.text) and self.text[self.pos + 1] in 'xX':
            self.pos += 2
            while self.pos < len(self.text) and self.text[self.pos] in '0123456789abcdefABCDEF':
                self.pos += 1
            self.tokens.append(Token(TokenType.Integer, self.text[start:self.pos], self.line))
            return

        while self.pos < len(self.text) and (self.text[self.pos].isdigit() or self.text[self.pos] == '.'):
            if self.text[self.pos] == '.':
                is_float = True
            self.pos += 1
        # Handle suffix like U, L, UL, etc
        while self.pos < len(self.text) and self.text[self.pos] in 'uUlLfF':
            self.pos += 1

        tok_type = TokenType.Float if is_float else TokenType.Integer
        self.tokens.append(Token(tok_type, self.text[start:self.pos], self.line))

    def _read_symbol(self):
        start = self.pos
        while self.pos < len(self.text) and (self.text[self.pos].isalnum() or self.text[self.pos] == '_'):
            self.pos += 1
        self.tokens.append(Token(TokenType.Symbol, self.text[start:self.pos], self.line))

    def peek(self):
        if self._index < len(self.tokens):
            return self.tokens[self._index]
        return Token(TokenType.EOF, '', self.line)

    def next(self):
        tok = self.peek()
        self._index += 1
        return tok

    def expect(self, tok_type, value=None):
        tok = self.next()
        if tok.type != tok_type:
            raise SyntaxError(f"Expected {tok_type}, got {tok} at line {tok.line}")
        if value is not None and tok.value != value:
            raise SyntaxError(f"Expected '{value}', got '{tok.value}' at line {tok.line}")
        return tok

    def match(self, tok_type, value=None):
        tok = self.peek()
        if tok.type == tok_type and (value is None or tok.value == value):
            self._index += 1
            return tok
        return None

    def at_end(self):
        return self.peek().type == TokenType.EOF
