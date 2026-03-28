"""Built-in C preprocessor: strips comments, captures #defines, handles conditionals."""

import re


class Preprocessor:
    """Strip comments, capture #defines, handle conditionals and multiline macros."""

    def __init__(self):
        self.defines = {}

    def process(self, source_text):
        """Process source text: strip comments, capture defines, return clean text."""
        text = self._strip_comments(source_text)
        lines = text.split('\n')
        clean_lines = []
        # Conditional compilation stack: list of bools (True = include lines)
        self._cond_stack = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # Handle multiline macros (backslash continuation)
            while line.rstrip().endswith('\\') and i + 1 < len(lines):
                line = line.rstrip()[:-1] + ' ' + lines[i + 1].strip()
                i += 1
            stripped = line.strip()
            if stripped.startswith('#ifdef '):
                sym = stripped[len('#ifdef '):].strip()
                self._cond_stack.append(sym in self.defines)
                clean_lines.append('')
            elif stripped.startswith('#ifndef '):
                sym = stripped[len('#ifndef '):].strip()
                self._cond_stack.append(sym not in self.defines)
                clean_lines.append('')
            elif stripped.startswith('#if '):
                # Simple #if: treat non-zero defines as true
                expr = stripped[len('#if '):].strip()
                val = self._eval_if_expr(expr)
                self._cond_stack.append(val)
                clean_lines.append('')
            elif stripped == '#else':
                if self._cond_stack:
                    self._cond_stack[-1] = not self._cond_stack[-1]
                clean_lines.append('')
            elif stripped.startswith('#elif '):
                if self._cond_stack:
                    # Only consider elif if we haven't already taken a branch
                    expr = stripped[len('#elif '):].strip()
                    self._cond_stack[-1] = self._eval_if_expr(expr)
                clean_lines.append('')
            elif stripped == '#endif':
                if self._cond_stack:
                    self._cond_stack.pop()
                clean_lines.append('')
            elif not self._is_active():
                clean_lines.append('')  # In excluded conditional block
            elif stripped.startswith('#define'):
                self._capture_define(stripped)
                clean_lines.append('')
            elif stripped.startswith('#'):
                clean_lines.append('')  # skip other preprocessor directives
            else:
                clean_lines.append(line)
            i += 1
        return '\n'.join(clean_lines)

    def _is_active(self):
        """Check if current position is in an active conditional block."""
        return all(self._cond_stack)

    def _eval_if_expr(self, expr):
        """Simple evaluation of #if expressions: defined(X), numeric, symbol lookup."""
        expr = expr.strip()
        # Handle defined(X) or defined X
        m = re.match(r'defined\s*\(\s*(\w+)\s*\)', expr)
        if m:
            return m.group(1) in self.defines
        m = re.match(r'defined\s+(\w+)', expr)
        if m:
            return m.group(1) in self.defines
        # Handle !defined(X)
        m = re.match(r'!\s*defined\s*\(\s*(\w+)\s*\)', expr)
        if m:
            return m.group(1) not in self.defines
        # Simple numeric or symbol
        if expr.isdigit():
            return int(expr) != 0
        if expr in self.defines:
            val = self.defines[expr]
            if isinstance(val, str) and val.isdigit():
                return int(val) != 0
            return True
        return False

    def _strip_comments(self, text):
        """Remove both // and /* */ comments."""
        result = []
        i = 0
        in_string = False
        string_char = None
        while i < len(text):
            if in_string:
                if text[i] == '\\' and i + 1 < len(text):
                    result.append(text[i:i+2])
                    i += 2
                    continue
                if text[i] == string_char:
                    in_string = False
                result.append(text[i])
                i += 1
            elif text[i] in ('"', "'"):
                in_string = True
                string_char = text[i]
                result.append(text[i])
                i += 1
            elif text[i:i+2] == '//':
                # Line comment - skip to end of line
                while i < len(text) and text[i] != '\n':
                    i += 1
                result.append('\n')
                if i < len(text):
                    i += 1
            elif text[i:i+2] == '/*':
                # Block comment
                i += 2
                while i < len(text) - 1 and text[i:i+2] != '*/':
                    if text[i] == '\n':
                        result.append('\n')
                    i += 1
                if i < len(text) - 1:
                    i += 2
            else:
                result.append(text[i])
                i += 1
        return ''.join(result)

    def _capture_define(self, line):
        """Parse a #define line and store name->value."""
        m = re.match(r'#define\s+(\w+)\s*(.*)', line)
        if m:
            name = m.group(1)
            value = m.group(2).strip()
            if value:
                self.defines[name] = value
            else:
                self.defines[name] = ''
