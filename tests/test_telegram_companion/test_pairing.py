from __future__ import annotations

import time
import pytest

from agent_ai.runtime.telegram.pairing import (
    PairingManager,
    PairingSession,
    generate_qr_ascii,
    generate_qr_svg,
)


def test_pairing_session_creation():
    manager = PairingManager(ttl_seconds=300)
    session = manager.create_session(bot_username="MyAegis_bot")

    assert session.token is not None
    assert len(session.token) >= 6
    assert session.deep_link == f"https://t.me/MyAegis_bot?start=pair_{session.token}"
    assert session.is_expired() is False
    assert manager.get_active_session() == session


def test_pairing_session_expiration():
    session = PairingSession(
        token="expired123",
        bot_username="MyAegis_bot",
        created_at=time.time() - 301,
        ttl_seconds=300,
    )
    assert session.is_expired() is True


def test_validate_and_consume_token():
    manager = PairingManager(ttl_seconds=300)
    session = manager.create_session(bot_username="MyAegis_bot")

    # Valid token succeeds
    assert manager.validate_token(session.token) is True

    # Single-use: Second validation fails
    assert manager.validate_token(session.token) is False

    # Random unknown token fails
    assert manager.validate_token("unknown_xyz") is False


def test_validate_expired_token_fails():
    manager = PairingManager(ttl_seconds=1)
    session = manager.create_session(bot_username="MyAegis_bot")
    time.sleep(1.05)

    assert manager.validate_token(session.token) is False


def test_generate_qr_svg():
    svg_code = generate_qr_svg("https://t.me/MyAegis_bot?start=pair_test")
    assert "<svg" in svg_code
    assert "</svg>" in svg_code
    assert "xmlns" in svg_code


def test_generate_qr_ascii():
    ascii_qr = generate_qr_ascii("https://t.me/MyAegis_bot?start=pair_test")
    assert isinstance(ascii_qr, str)
    assert len(ascii_qr.strip()) > 0
