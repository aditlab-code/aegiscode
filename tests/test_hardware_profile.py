"""Unit tests untuk deteksi profil perangkat keras (Phase 2.1)."""

from agent_ai.runtime.telemetry.hardware import (
    EmbedProfile,
    detect_embed_profile,
    _total_ram_gb,
)


def test_detect_embed_profile_default():
    profile = detect_embed_profile()
    assert isinstance(profile, EmbedProfile)
    assert 1 <= profile.threads <= 8
    assert profile.batch_size in (8, 16, 32)
    assert profile.cpu_count >= 1


def test_detect_embed_profile_threads_allocation(monkeypatch):
    # Bila CPU = 1 core, threads minimal 1
    monkeypatch.setattr("os.cpu_count", lambda: 1)
    p1 = detect_embed_profile()
    assert p1.threads == 1

    # Bila CPU = 4 core, threads = 4 - 1 = 3
    monkeypatch.setattr("os.cpu_count", lambda: 4)
    p4 = detect_embed_profile()
    assert p4.threads == 3

    # Bila CPU = 32 core, threads dibatasi maksimal 8
    monkeypatch.setattr("os.cpu_count", lambda: 32)
    p32 = detect_embed_profile()
    assert p32.threads == 8


def test_detect_embed_profile_ram_tiers(monkeypatch):
    monkeypatch.setattr("os.cpu_count", lambda: 8)

    # RAM 32 GB -> batch_size 32
    monkeypatch.setattr("agent_ai.runtime.telemetry.hardware._total_ram_gb", lambda: 32.0)
    p32 = detect_embed_profile()
    assert p32.batch_size == 32

    # RAM 12 GB -> batch_size 16
    monkeypatch.setattr("agent_ai.runtime.telemetry.hardware._total_ram_gb", lambda: 12.0)
    p12 = detect_embed_profile()
    assert p12.batch_size == 16

    # RAM 4 GB -> batch_size 8
    monkeypatch.setattr("agent_ai.runtime.telemetry.hardware._total_ram_gb", lambda: 4.0)
    p4 = detect_embed_profile()
    assert p4.batch_size == 8

    # RAM None -> fallback batch_size konservatif
    monkeypatch.setattr("agent_ai.runtime.telemetry.hardware._total_ram_gb", lambda: None)
    p_none = detect_embed_profile()
    assert p_none.batch_size in (8, 16)
