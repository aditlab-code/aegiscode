"""Resolusi lokasi penyimpanan database vektor dan cache model.

Murni menggunakan .aegis/vectors.db pada workspace.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union

from agent_ai.config.settings import EMBED_CACHE

_REPO_ROOT = Path(__file__).resolve().parents[4]


PathLike = Union[str, os.PathLike[str]]

VECTORS_DB_NAME = "vectors.db"
AEGIS_DIR = ".aegis"


def resolve_vectors_db(root: PathLike) -> Path:
    """Tentukan jalur berkas vectors.db pada target workspace (<root>/.aegis/vectors.db)."""
    root_path = Path(root).resolve()
    return root_path / AEGIS_DIR / VECTORS_DB_NAME


def resolve_model_cache() -> Path:
    """Tentukan direktori penyimpanan cache model fastembed.

    Prioritas:
        1. Variabel lingkungan / konfigurasi EMBED_CACHE (bila diisi).
        2. Direktori bersama: <AEGIS_ROOT>/data/models/
    """
    if EMBED_CACHE and str(EMBED_CACHE).strip():
        return Path(str(EMBED_CACHE).strip()).resolve()
    return _REPO_ROOT / "data" / "models"


__all__ = [
    "resolve_vectors_db",
    "resolve_model_cache",
    "VECTORS_DB_NAME",
    "AEGIS_DIR",
]

