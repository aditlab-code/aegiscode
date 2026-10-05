"""Resolusi lokasi penyimpanan database vektor dan cache model.

Mendukung backward compatibility dua arah: .aegis/ (primer) dengan fallback
transparan ke .aether/.
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
AETHER_DIR = ".aether"


def resolve_vectors_db(root: PathLike) -> Path:
    """Tentukan jalur berkas vectors.db pada target workspace.

    Aturan:
        1. Bila <root>/.aegis/vectors.db sudah ada, gunakan .aegis/vectors.db.
        2. Bila <root>/.aegis/vectors.db belum ada tetapi <root>/.aether/vectors.db ada,
           gunakan .aether/vectors.db (fallback transparan).
        3. Bila belum ada di kedua lokasi, gunakan .aegis/vectors.db sebagai target baru.
    """
    root_path = Path(root).resolve()
    aegis_db = root_path / AEGIS_DIR / VECTORS_DB_NAME
    aether_db = root_path / AETHER_DIR / VECTORS_DB_NAME

    if aegis_db.exists():
        return aegis_db
    if aether_db.exists():
        return aether_db
    return aegis_db


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
    "AETHER_DIR",
]
