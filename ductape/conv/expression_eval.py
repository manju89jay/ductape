"""Constant integer expression evaluator."""

import re


class ExpressionEvaluator:
    """Evaluate constant integer expressions with symbol substitution."""

    def __init__(self, symbol_table=None):
        self.symbols = dict(symbol_table) if symbol_table else {}

    def add_symbol(self, name, value):
        self.symbols[name] = value

    def evaluate(self, expr):
        """Evaluate an expression string to an integer, or return None."""
        if expr is None or expr == '':
            return None
        try:
            resolved = self._substitute_symbols(str(expr))
            return self._eval_expr(resolved)
        except Exception:
            return None

    def _substitute_symbols(self, expr):
        """Replace known symbol names with their integer values."""
        def replacer(m):
            # Skip hex literals like 0xFF
            start = m.start()
            if start > 0 and expr[start - 1] in ('0',) and start >= 2 and expr[start - 1:start + 1].startswith('x'):
                return m.group(0)
            name = m.group(0)
            if name in self.symbols:
                val = self.symbols[name]
                if isinstance(val, int):
                    return str(val)
                # Try to evaluate the symbol's value recursively
                resolved = self._substitute_symbols(str(val))
                result = self._eval_expr(resolved)
                if result is not None:
                    self.symbols[name] = result  # cache
                    return str(result)
                return str(val)
            return name
        # Use negative lookbehind to avoid matching hex suffixes like xFF in 0xFF
        return re.sub(r'(?<![0-9x])\b[A-Za-z_]\w*', replacer, expr)

    def _eval_expr(self, expr):
        """Safely evaluate an integer expression."""
        expr = expr.strip()
        if not expr:
            return None
        # Only allow safe characters
        if not re.match(r'^[\dA-Fa-fxX\s\+\-\*/%\(\)&\|~\^<>]+$', expr):
            return None
        try:
            # Replace / with // for integer division (but not // which stays)
            int_expr = re.sub(r'(?<!/)/(?!/)', '//', expr)
            result = eval(int_expr, {"__builtins__": {}}, {})
            if isinstance(result, (int, float, bool)):
                return int(result)
            return None
        except Exception:
            return None
