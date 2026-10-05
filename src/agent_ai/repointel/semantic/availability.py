"""Pemeriksaan ketersediaan dependensi pencarian semantik (zero-dependency)."""

from __future__ import annotations

from typing import Tuple


def is_available() -> Tuple[bool, str]:
    """Periksa apakah dependensi opsional pencarian semantik telah terpasang.

    Returns:
        Tuple (tersedia: bool, pesan_alasan: str)
    """
    missing = []
    for pkg in ("fastembed", "langchain_core", "langchain_community"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        return (
            False,
            f"Dependensi pencarian semantik ({', '.join(missing)}) belum terpasang. "
            "Pasang dependensi dengan perintah: pip install aegis-agent[semantic]",
        )
    return True, ""


__all__ = ["is_available"]
