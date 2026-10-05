"""Deteksi profil perangkat keras deterministik untuk pipeline embedding lokal.

Menentukan alokasi thread dan batch size optimal untuk fastembed/onnxruntime
tanpa dependensi berat pihak ketiga (seperti psutil).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class EmbedProfile:
    """Profil alokasi perangkat keras untuk inferensi embedding lokal.

    Attributes:
        threads: Jumlah thread komputasi untuk model ONNX / embedding (>= 1).
        batch_size: Ukuran batch pemrosesan teks per putaran inferensi (>= 1).
        total_ram_gb: Perkiraan RAM fisik sistem dalam Gigabyte (opsional).
        cpu_count: Jumlah core logis CPU yang terdeteksi.
    """

    threads: int
    batch_size: int
    total_ram_gb: Optional[float] = None
    cpu_count: int = 1


def _total_ram_gb() -> Optional[float]:
    """Deteksi total RAM fisik dalam Gigabyte dengan pendekatan zero-dependency.

    Mendukung POSIX (Linux/macOS) via os.sysconf, dan Windows via ctypes.
    Bila terjadi kegagalan atau platform tidak didukung, mengembalikan None.
    """
    try:
        if hasattr(os, "sysconf"):
            if "SC_PAGE_SIZE" in os.sysconf_names and "SC_PHYS_PAGES" in os.sysconf_names:
                page_size = os.sysconf("SC_PAGE_SIZE")
                total_pages = os.sysconf("SC_PHYS_PAGES")
                if page_size > 0 and total_pages > 0:
                    return float((page_size * total_pages) / (1024**3))
    except (ValueError, OSError, AttributeError):
        pass

    if sys.platform.startswith("win"):
        try:
            import ctypes

            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = _MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):  # type: ignore[attr-defined]
                return float(stat.ullTotalPhys / (1024**3))
        except Exception:
            pass

    return None


def detect_embed_profile() -> EmbedProfile:
    """Deteksi profil perangkat keras untuk alokasi thread dan batch size fastembed.

    Aturan:
        - Threads: Menggunakan (cores - 1) untuk menyisakan minimal 1 core bagi OS/LLM/I-O,
          dibatasi antara 1 hingga 8 thread.
        - Batch size:
            - >= 16 GB RAM -> batch size 32
            - >= 8 GB RAM  -> batch size 16
            - < 8 GB RAM / tidak terdeteksi -> batch size 8
    """
    cores = os.cpu_count() or 2
    ram_gb = _total_ram_gb()

    # Sisakan minimal 1 core untuk sistem, batas atas 8 thread untuk mencegah thrashing
    threads = max(1, min(cores - 1, 8))

    if ram_gb is not None:
        if ram_gb >= 15.5:
            batch_size = 32
        elif ram_gb >= 7.5:
            batch_size = 16
        else:
            batch_size = 8
    else:
        # Fallback konservatif bila RAM tidak terdeteksi
        batch_size = 16 if cores >= 8 else 8

    return EmbedProfile(
        threads=threads,
        batch_size=batch_size,
        total_ram_gb=round(ram_gb, 2) if ram_gb is not None else None,
        cpu_count=cores,
    )


__all__ = ["EmbedProfile", "detect_embed_profile"]
