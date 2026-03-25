"""Tests for the C preprocessor."""

from ductape.conv.preprocessor import Preprocessor


def test_strip_line_comment():
    pp = Preprocessor()
    result = pp.process("int x; // comment\nint y;")
    assert "// comment" not in result
    assert "int x;" in result
    assert "int y;" in result


def test_strip_block_comment():
    pp = Preprocessor()
    result = pp.process("int x; /* block\ncomment */ int y;")
    assert "/* block" not in result
    assert "int y;" in result


def test_capture_simple_define():
    pp = Preprocessor()
    pp.process("#define FOO 42\n")
    assert pp.defines["FOO"] == "42"


def test_capture_define_expression():
    pp = Preprocessor()
    pp.process("#define SIZE (32 + 4)\n")
    assert pp.defines["SIZE"] == "(32 + 4)"


def test_multiline_define():
    pp = Preprocessor()
    pp.process("#define FOO \\\n  42\n")
    assert pp.defines["FOO"] == "42"


def test_define_no_value():
    pp = Preprocessor()
    pp.process("#define GUARD_H\n")
    assert pp.defines["GUARD_H"] == ""


def test_skip_includes_and_pragmas():
    pp = Preprocessor()
    result = pp.process('#include "foo.h"\n#pragma once\nint x;')
    assert '#include' not in result
    assert '#pragma' not in result
    assert 'int x;' in result


def test_preserves_string_with_slash():
    pp = Preprocessor()
    result = pp.process('char* s = "hello // world";')
    assert '"hello // world"' in result


def test_nested_block_comments():
    pp = Preprocessor()
    result = pp.process("/* outer /* still comment */ int x;")
    assert "int x;" in result


def test_multiple_defines():
    pp = Preprocessor()
    pp.process("#define A 1\n#define B 2\n#define C 3\n")
    assert pp.defines["A"] == "1"
    assert pp.defines["B"] == "2"
    assert pp.defines["C"] == "3"
