#!/usr/bin/env python3

"""
YAML configuration loader utility.
"""

from pathlib import Path
from typing import Any, Dict

try:
    import yaml  # type: ignore
except Exception as e:
    raise ImportError("PyYAML is required: pip install pyyaml") from e


def load_yaml_config(path: str | Path) -> Dict[str, Any]:
    """
    Load a YAML file into a Python dict.

    Args:
        path: path to a YAML configuration file.

    Returns:
        A dictionary with the parsed YAML content. If the file is empty,
        an empty dict is returned.
    """
    with Path(path).expanduser().open("r") as f:
        data = yaml.safe_load(f)
    return dict(data) if isinstance(data, dict) else {}
