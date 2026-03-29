"""Extract headers from C/C++ package manager packages (FR-10).

Aggregates header files from Conan or vcpkg package directories into a flat,
versioned folder structure suitable for subsequent parsing by ductape.

Output layout:
    interfaces/<version>/<source_tag>/<header_files>
"""

import os
import shutil
import glob as glob_mod


def extract_dependencies(packages, output_dir):
    """Extract header files from package directories.

    Args:
        packages: list of dicts with keys:
            - path: path to the package root (e.g. conan cache dir)
            - version_tag: version label (e.g. "v1")
            - source_tag: source identifier (e.g. "telemetry")
            - include_patterns: optional list of glob patterns (default ["*.h"])
        output_dir: root output directory for extracted headers
    Returns:
        dict mapping (version_tag, source_tag) -> list of extracted file paths
    """
    results = {}
    for pkg in packages:
        pkg_path = pkg['path']
        version_tag = pkg['version_tag']
        source_tag = pkg.get('source_tag', os.path.basename(pkg_path))
        patterns = pkg.get('include_patterns', ['*.h'])

        dest_dir = os.path.join(output_dir, version_tag, source_tag)
        os.makedirs(dest_dir, exist_ok=True)

        extracted = []
        for pattern in patterns:
            # Search recursively for matching headers
            search = os.path.join(pkg_path, '**', pattern)
            for src_file in glob_mod.glob(search, recursive=True):
                if os.path.isfile(src_file):
                    fname = os.path.basename(src_file)
                    dst_file = os.path.join(dest_dir, fname)
                    shutil.copy2(src_file, dst_file)
                    extracted.append(dst_file)

        results[(version_tag, source_tag)] = extracted

    return results


def extract_from_config(config, output_dir):
    """Extract dependencies defined in config's 'dependencies' section.

    Config format:
        dependencies:
          - path: /path/to/package
            version_tag: v1
            source_tag: telemetry
            include_patterns:
              - "*.h"
              - "*.hpp"

    Args:
        config: loaded config dict
        output_dir: root output directory (typically interfaces/)
    Returns:
        dict mapping (version_tag, source_tag) -> list of extracted file paths
    """
    deps = config.get('dependencies', [])
    if not deps:
        return {}

    base_dir = config.get('_config_dir', '.')
    resolved = []
    for dep in deps:
        pkg_path = dep['path']
        if not os.path.isabs(pkg_path):
            pkg_path = os.path.join(base_dir, pkg_path)
        resolved.append({
            'path': pkg_path,
            'version_tag': dep['version_tag'],
            'source_tag': dep.get('source_tag', os.path.basename(pkg_path)),
            'include_patterns': dep.get('include_patterns', ['*.h']),
        })

    return extract_dependencies(resolved, output_dir)
