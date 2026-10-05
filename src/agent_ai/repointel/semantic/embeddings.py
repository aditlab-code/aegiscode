"""Wrapper untuk inisialisasi modul fastembed dan profil inferensi lokal."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from agent_ai.config.settings import EMBED_MODEL
from agent_ai.repointel.semantic.paths import resolve_model_cache



def build_embeddings(
    model_name: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    max_length: int = 512,
) -> Any:
    """Inisialisasi FastEmbedEmbeddings LangChain dengan konfigurasi profil hardware lokal.

    Args:
        model_name: Nama model HuggingFace / FastEmbed (default dari settings.EMBED_MODEL).
        cache_dir: Direktori penyimpanan model onnx lokal.
        max_length: Batas token panjang konteks (default 512 untuk bge-small).

    Raises:
        ImportError: Bila paket fastembed atau langchain_community belum terpasang.
    """
    try:
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    except ImportError as e:
        raise ImportError(
            "Modul 'fastembed' atau 'langchain_community' tidak ditemukan. "
            "Pasang dependensi opsional dengan: pip install aegis-agent[semantic]"
        ) from e

    from agent_ai.runtime.telemetry.hardware import detect_embed_profile

    profile = detect_embed_profile()

    chosen_model = model_name or EMBED_MODEL
    chosen_cache = cache_dir or resolve_model_cache()
    chosen_cache.mkdir(parents=True, exist_ok=True)

    return FastEmbedEmbeddings(
        model_name=chosen_model,
        cache_dir=str(chosen_cache),
        threads=profile.threads,
        batch_size=profile.batch_size,
        max_length=max_length,
    )


__all__ = ["build_embeddings"]
