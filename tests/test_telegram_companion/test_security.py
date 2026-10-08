from __future__ import annotations

import json
import os
import stat
import pytest
from pathlib import Path

from agent_ai.runtime.telegram.security import (
    TelegramSecurityManager,
    PairedUser,
)


@pytest.fixture
def temp_storage_path(tmp_path: Path) -> Path:
    return tmp_path / "telegram_paired.json"


def test_pairing_status_initial(temp_storage_path: Path):
    manager = TelegramSecurityManager(storage_path=temp_storage_path, env_whitelist="")
    status = manager.get_status()
    assert status.is_paired is False
    assert status.paired_user is None
    assert manager.is_authorized(12345) is False


def test_save_and_authorize_paired_user(temp_storage_path: Path):
    manager = TelegramSecurityManager(storage_path=temp_storage_path, env_whitelist="")
    user = manager.save_paired_user(user_id=12345, username="adit", first_name="Adit")

    assert user.user_id == 12345
    assert user.username == "adit"
    assert user.first_name == "Adit"

    # Status check
    status = manager.get_status()
    assert status.is_paired is True
    assert status.paired_user is not None
    assert status.paired_user.user_id == 12345

    # Authorization check
    assert manager.is_authorized(12345) is True
    assert manager.is_authorized(99999) is False  # Unauthorized stranger

    # File permission check (0600)
    assert temp_storage_path.exists()
    file_mode = stat.S_IMODE(os.stat(temp_storage_path).st_mode)
    assert file_mode == 0o600


def test_unlink_paired_user(temp_storage_path: Path):
    manager = TelegramSecurityManager(storage_path=temp_storage_path, env_whitelist="")
    manager.save_paired_user(user_id=12345, username="adit")
    assert manager.is_authorized(12345) is True

    manager.unlink()
    status = manager.get_status()
    assert status.is_paired is False
    assert status.paired_user is None
    assert manager.is_authorized(12345) is False


def test_env_whitelist_fallback(temp_storage_path: Path):
    manager = TelegramSecurityManager(storage_path=temp_storage_path, env_whitelist="111,222, 333")
    assert manager.is_authorized(111) is True
    assert manager.is_authorized(222) is True
    assert manager.is_authorized(333) is True
    assert manager.is_authorized(444) is False


def test_username_whitelist_support(temp_storage_path: Path):
    manager = TelegramSecurityManager(storage_path=temp_storage_path, env_whitelist="@vizzyoc, @admin_dev")
    # Akun dengan username vizzyoc otomatis terotorisasi
    assert manager.is_authorized(user_id=77777, username="vizzyoc") is True
    assert manager.is_authorized(user_id=88888, username="@admin_dev") is True
    # Akun lain ditolak
    assert manager.is_authorized(user_id=99999, username="stranger_user") is False
