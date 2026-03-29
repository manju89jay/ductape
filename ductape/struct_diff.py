"""Structural diff between generated outputs (Phase 14).

Compares two generated output directories and reports structural
differences in type definitions and converter files.
"""

import os
import filecmp


def compute_struct_diff(dir1, dir2):
    """Compare two generated output directories structurally.

    Args:
        dir1: First output directory
        dir2: Second output directory
    Returns:
        dict with 'only_in_dir1', 'only_in_dir2', 'differing', 'identical'
    """
    files1 = _collect_files(dir1)
    files2 = _collect_files(dir2)

    set1 = set(files1.keys())
    set2 = set(files2.keys())

    only_in_dir1 = sorted(set1 - set2)
    only_in_dir2 = sorted(set2 - set1)

    differing = []
    identical = []
    for rel_path in sorted(set1 & set2):
        if filecmp.cmp(files1[rel_path], files2[rel_path], shallow=False):
            identical.append(rel_path)
        else:
            differing.append(rel_path)

    return {
        'only_in_dir1': only_in_dir1,
        'only_in_dir2': only_in_dir2,
        'differing': differing,
        'identical': identical,
    }


def format_struct_diff(diff, dir1, dir2):
    """Format a structural diff as human-readable text."""
    lines = [
        "Structural Diff Report",
        "=" * 50,
        f"  Dir 1: {dir1}",
        f"  Dir 2: {dir2}",
        "",
    ]

    if diff['only_in_dir1']:
        lines.append(f"Only in dir1 ({len(diff['only_in_dir1'])} files):")
        for f in diff['only_in_dir1']:
            lines.append(f"  - {f}")

    if diff['only_in_dir2']:
        lines.append(f"\nOnly in dir2 ({len(diff['only_in_dir2'])} files):")
        for f in diff['only_in_dir2']:
            lines.append(f"  + {f}")

    if diff['differing']:
        lines.append(f"\nDiffering ({len(diff['differing'])} files):")
        for f in diff['differing']:
            lines.append(f"  ~ {f}")

    lines.append(f"\nIdentical: {len(diff['identical'])} files")

    if not diff['only_in_dir1'] and not diff['only_in_dir2'] and not diff['differing']:
        lines.append("\nDirectories are structurally identical.")

    return '\n'.join(lines)


def run_struct_diff(dir1, dir2):
    """Run structural diff and print results."""
    diff = compute_struct_diff(dir1, dir2)
    print(format_struct_diff(diff, dir1, dir2))


def _collect_files(root_dir):
    """Collect all files with relative paths."""
    files = {}
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, root_dir)
            files[rel_path] = full_path
    return files
