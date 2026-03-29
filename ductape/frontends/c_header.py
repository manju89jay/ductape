"""C header parser frontend (FR-22).

Wraps the existing conv/parser.py as a pluggable ParserFrontend.
"""

import os
from ductape.frontends.frontend_base import ParserFrontend, register_frontend
from ductape.conv.parser import Parser


@register_frontend
class CHeaderFrontend(ParserFrontend):
    """Parser frontend for C/C++ header files."""

    format_id = "c_header"

    def parse(self, schema_path, config):
        """Parse C header files from a directory.

        Args:
            schema_path: Path to directory containing .h files
            config: Full config dict (uses additional_includes, _config_dir)
        Returns:
            Populated TypeContainer
        """
        base_dir = config.get('_config_dir', '.')
        additional_includes = config.get('additional_includes', [])
        parser = Parser()

        all_text = ""

        # Read additional include files (e.g. platform_types.h)
        for inc_dir in additional_includes:
            inc_path = os.path.join(base_dir, inc_dir)
            if os.path.isdir(inc_path):
                for fname in sorted(os.listdir(inc_path)):
                    if fname.endswith('.h'):
                        fpath = os.path.join(inc_path, fname)
                        with open(fpath) as f:
                            all_text += f.read() + "\n"

        # Read header files from schema_path
        header_dir = schema_path
        if not os.path.isabs(header_dir):
            header_dir = os.path.join(base_dir, header_dir)

        if os.path.isdir(header_dir):
            for fname in sorted(os.listdir(header_dir)):
                if fname.endswith('.h'):
                    fpath = os.path.join(header_dir, fname)
                    with open(fpath) as f:
                        all_text += f.read() + "\n"
        elif os.path.isfile(header_dir):
            with open(header_dir) as f:
                all_text += f.read() + "\n"

        return parser.parse(all_text)

    def file_extensions(self):
        return ['.h', '.hpp']
