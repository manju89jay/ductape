"""Built-in C preprocessor: strips comments, captures #defines."""

import re


class Preprocessor:
    """Strip comments, capture #defines, handle multiline macros."""

    def __init__(self):
        self.defines = {}

    def process(self, source_text):
        """Process source text: strip comments, capture defines, return clean text."""
        text = self._strip_comments(source_text)
        lines = text.split('\n')
        clean_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # Handle multiline macros (backslash continuation)
            while line.rstrip().endswith('\\') and i + 1 < len(lines):
                line = line.rstrip()[:-1] + ' ' + lines[i + 1].strip()
                i += 1
            stripped = line.strip()
            if stripped.startswith('#define'):
                self._capture_define(stripped)
                clean_lines.append('')  # preserve line numbering
            elif stripped.startswith('#'):
                clean_lines.append('')  # skip other preprocessor directives
            else:
                clean_lines.append(line)
            i += 1
        return '\n'.join(clean_lines)

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
                result.append('\n')  # preserve newline
                if i < len(text):
                    i += 1  # skip the newline
            elif text[i:i+2] == '/*':
                # Block comment
                i += 2
                while i < len(text) - 1 and text[i:i+2] != '*/':
                    if text[i] == '\n':
                        result.append('\n')  # preserve line numbering
                    i += 1
                if i < len(text) - 1:
                    i += 2  # skip */
            else:
                result.append(text[i])
                i += 1
        return ''.join(result)

    def _capture_define(self, line):
        """Parse a #define line and store name->value."""
        # Match: #define NAME VALUE
        m = re.match(r'#define\s+(\w+)\s*(.*)', line)
        if m:
            name = m.group(1)
            value = m.group(2).strip()
            if value:
                self.defines[name] = value
            else:
                self.defines[name] = ''
