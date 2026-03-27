"""Diff report between version snapshots (FR-12).

When a previous version_overview.json is supplied, produces a diff report
listing which interface version numbers changed between releases.
"""

import json
import os


def load_version_overview(path):
    """Load a version_overview.json file."""
    with open(path, 'r') as f:
        return json.load(f)


def compute_diff(previous, current):
    """Compute differences between two version overview snapshots.

    Args:
        previous: dict from previous version_overview.json
        current: dict from current version_overview.json
    Returns:
        dict with keys 'added', 'removed', 'changed', 'unchanged'
    """
    prev_types = set(previous.keys())
    curr_types = set(current.keys())

    added = {}
    for t in sorted(curr_types - prev_types):
        added[t] = current[t]

    removed = {}
    for t in sorted(prev_types - curr_types):
        removed[t] = previous[t]

    changed = {}
    unchanged = []
    for t in sorted(prev_types & curr_types):
        prev_versions = set(previous[t]['versions'])
        curr_versions = set(current[t]['versions'])
        if prev_versions != curr_versions:
            changed[t] = {
                'previous_versions': previous[t]['versions'],
                'current_versions': current[t]['versions'],
                'added_versions': sorted(curr_versions - prev_versions),
                'removed_versions': sorted(prev_versions - curr_versions),
            }
        else:
            unchanged.append(t)

    return {
        'added': added,
        'removed': removed,
        'changed': changed,
        'unchanged': unchanged,
    }


def generate_diff_report(previous_path, current_path):
    """Generate a diff report between two version overview files.

    Args:
        previous_path: path to previous version_overview.json
        current_path: path to current version_overview.json
    Returns:
        dict with diff results
    """
    previous = load_version_overview(previous_path)
    current = load_version_overview(current_path)
    return compute_diff(previous, current)


def format_diff_report(diff):
    """Format a diff report as human-readable text.

    Args:
        diff: dict from compute_diff()
    Returns:
        string with formatted report
    """
    lines = ["Version Diff Report", "=" * 40]

    if diff['added']:
        lines.append("\nAdded types:")
        for t, info in diff['added'].items():
            lines.append(f"  + {t}: versions {info['versions']}")

    if diff['removed']:
        lines.append("\nRemoved types:")
        for t, info in diff['removed'].items():
            lines.append(f"  - {t}: versions {info['versions']}")

    if diff['changed']:
        lines.append("\nChanged types:")
        for t, info in diff['changed'].items():
            lines.append(f"  ~ {t}:")
            if info['added_versions']:
                lines.append(f"      added versions: {info['added_versions']}")
            if info['removed_versions']:
                lines.append(f"      removed versions: {info['removed_versions']}")
            lines.append(f"      {info['previous_versions']} -> {info['current_versions']}")

    if diff['unchanged']:
        lines.append(f"\nUnchanged types: {', '.join(diff['unchanged'])}")

    return '\n'.join(lines)
