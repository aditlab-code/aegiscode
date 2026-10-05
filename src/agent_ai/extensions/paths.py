"""Path resolver for Extension System (no hardcode).

Resolves AegisCode root and Extension runtime directory in a portable way.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union

ProjectPath = Union[str, "os.PathLike[str]"]

# src/agent_ai/extensions/paths.py -> parents[3] = repo root (AEGIS_ROOT)
_AEGIS_ROOT: Path = Path(__file__).resolve().parents[3]

#: Environment variable to override extensions dir or aegis root.
ENV_AEGIS_ROOT = "AEGIS_ROOT"
ENV_AEGIS_EXTENSIONS_DIR = "AEGIS_EXTENSIONS_DIR"
ENV_EXTENSIONS_DIR = "AEGIS_EXTENSIONS_DIR"


def get_aegis_root(explicit: ProjectPath | None = None) -> Path:
    """Return AegisCode root path.

    Priority:
        1. explicit argument
        2. env AEGIS_ROOT
        3. repo root computed from this file location
    """
    if explicit is not None and str(explicit).strip():
        return Path(str(explicit).strip())
    env = os.environ.get(ENV_AEGIS_ROOT, "")
    if isinstance(env, str) and env.strip():
        return Path(env.strip())
    return _AEGIS_ROOT


def get_extensions_dir(
    aegis_root: ProjectPath | None = None, explicit: ProjectPath | None = None
) -> Path:
    """Return extensions runtime directory.

    Priority:
        1. explicit
        2. env AEGIS_EXTENSIONS_DIR
        3. <AEGIS_ROOT>/Extension
    """
    if explicit is not None and str(explicit).strip():
        return Path(str(explicit).strip())
    env = os.environ.get(ENV_AEGIS_EXTENSIONS_DIR, "")
    if isinstance(env, str) and env.strip():
        return Path(env.strip())
    root = get_aegis_root(aegis_root)
    return root / "Extension"


def get_aegis_data_dir(aegis_root: ProjectPath | None = None) -> Path:
    """Return AegisCode data directory: <AEGIS_ROOT>/data (existing)."""
    return get_aegis_root(aegis_root) / "data"


def get_extensions_data_dir(aegis_root: ProjectPath | None = None) -> Path:
    """Return runtime extension data directory: <AEGIS_ROOT>/data/extensions."""
    return get_aegis_data_dir(aegis_root) / "extensions"


__all__ = [
    "get_aegis_root",
    "get_extensions_dir",
    "get_aegis_data_dir",
    "get_extensions_data_dir",
    "ENV_AEGIS_ROOT",
    "ENV_AEGIS_EXTENSIONS_DIR",
    "ENV_EXTENSIONS_DIR",
    "_AEGIS_ROOT",
]
