"""Tests for tokenizer."""

from ductape.conv.tokenizer import Tokenizer, TokenType


def test_symbol():
    t = Tokenizer("hello")
    tok = t.next()
    assert tok.type == TokenType.Symbol
    assert tok.value == "hello"


def test_integer():
    t = Tokenizer("42")
    tok = t.next()
    assert tok.type == TokenType.Integer
    assert tok.value == "42"


def test_hex_integer():
    t = Tokenizer("0xFF")
    tok = t.next()
    assert tok.type == TokenType.Integer
    assert tok.value == "0xFF"


def test_float():
    t = Tokenizer("3.14")
    tok = t.next()
    assert tok.type == TokenType.Float
    assert tok.value == "3.14"


def test_string():
    t = Tokenizer('"hello world"')
    tok = t.next()
    assert tok.type == TokenType.String
    assert tok.value == '"hello world"'


def test_special_chars():
    t = Tokenizer("{ } ; * [ ]")
    types = []
    while not t.at_end():
        tok = t.next()
        types.append(tok.value)
    assert types == ['{', '}', ';', '*', '[', ']']


def test_operators():
    t = Tokenizer("+ - /")
    types = []
    while not t.at_end():
        tok = t.next()
        assert tok.type == TokenType.Operator
        types.append(tok.value)
    assert types == ['+', '-', '/']


def test_eof():
    t = Tokenizer("")
    tok = t.next()
    assert tok.type == TokenType.EOF


def test_struct_tokens():
    t = Tokenizer("typedef struct { uint32 x; } Foo_t;")
    tokens = []
    while not t.at_end():
        tokens.append(t.next())
    names = [tok.value for tok in tokens]
    assert 'typedef' in names
    assert 'struct' in names
    assert 'uint32' in names
    assert 'Foo_t' in names


def test_match():
    t = Tokenizer("typedef struct")
    assert t.match(TokenType.Symbol, "typedef") is not None
    assert t.match(TokenType.Symbol, "struct") is not None
    assert t.at_end()
