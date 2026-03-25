"""Tests for expression evaluator."""

from ductape.conv.expression_eval import ExpressionEvaluator


def test_simple_integer():
    ev = ExpressionEvaluator()
    assert ev.evaluate("42") == 42


def test_addition():
    ev = ExpressionEvaluator()
    assert ev.evaluate("10 + 20") == 30


def test_complex_expression():
    ev = ExpressionEvaluator()
    assert ev.evaluate("(32 + 4) * 2") == 72


def test_symbol_substitution():
    ev = ExpressionEvaluator({"BASE_SIZE": 32})
    assert ev.evaluate("BASE_SIZE + 4") == 36


def test_chained_symbols():
    ev = ExpressionEvaluator({"BASE": 32, "BUF": "(BASE + 4)"})
    assert ev.evaluate("BUF / 2") == 18


def test_bitwise_operations():
    ev = ExpressionEvaluator()
    assert ev.evaluate("0xFF & 0x0F") == 15


def test_shift_operations():
    ev = ExpressionEvaluator()
    assert ev.evaluate("1 << 8") == 256


def test_modulo():
    ev = ExpressionEvaluator()
    assert ev.evaluate("17 % 5") == 2


def test_unknown_symbol_returns_none():
    ev = ExpressionEvaluator()
    assert ev.evaluate("UNKNOWN_VAR") is None


def test_empty_returns_none():
    ev = ExpressionEvaluator()
    assert ev.evaluate("") is None
    assert ev.evaluate(None) is None


def test_parentheses():
    ev = ExpressionEvaluator()
    assert ev.evaluate("(2 + 3) * (4 - 1)") == 15
