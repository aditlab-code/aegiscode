from __future__ import annotations

import json
import os
import stat
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PairedUser:
    """Informasi akun Telegram yang terhubung."""

    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    paired_at: float = 0.0


@dataclass
class PairingStatus:
    """Status otentikasi Telegram companion."""

    is_paired: bool
    paired_user: Optional[PairedUser] = None
    env_allowed_ids: list[int] = None

    def __post_init__(self):
        if self.env_allowed_ids is None:
            self.env_allowed_ids = []


class TelegramSecurityManager:
    """Pengelola whitelist dan persistensi pengguna Telegram AegisCode."""

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        env_whitelist: Optional[str] = None,
    ):
        if storage_path is None:
            storage_path = Path.cwd() / ".aegis" / "telegram_paired.json"
        self.storage_path = Path(storage_path)

        if env_whitelist is None:
            env_whitelist = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
        self.env_allowed_ids, self.env_allowed_usernames = self._parse_whitelist(env_whitelist)

    @staticmethod
    def _parse_whitelist(whitelist_str: str) -> tuple[set[int], set[str]]:
        ids: set[int] = set()
        usernames: set[str] = set()
        if not whitelist_str:
            return ids, usernames
        for part in whitelist_str.split(","):
            cleaned = part.strip()
            if not cleaned:
                continue
            if cleaned.isdigit() or (cleaned.startswith("-") and cleaned[1:].isdigit()):
                ids.add(int(cleaned))
            else:
                usernames.add(cleaned.lstrip("@").lower())
        return ids, usernames

    def _ensure_dir_secure(self) -> None:
        parent = self.storage_path.parent
        parent.mkdir(parents=True, exist_ok=True)

    def load_paired_user(self) -> Optional[PairedUser]:
        if not self.storage_path.exists():
            return None
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "user_id" not in data:
                return None
            return PairedUser(
                user_id=int(data["user_id"]),
                username=data.get("username"),
                first_name=data.get("first_name"),
                paired_at=float(data.get("paired_at", 0.0)),
            )
        except Exception:
            return None

    def save_paired_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
    ) -> PairedUser:
        self._ensure_dir_secure()
        user = PairedUser(
            user_id=int(user_id),
            username=username,
            first_name=first_name,
            paired_at=time.time(),
        )
        # Tulis ke file sementara lalu rename untuk atomicity
        tmp_path = self.storage_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(asdict(user), f, indent=2)

        # Set izin 0600 (hanya pemilik yang bisa membaca/menulis)
        os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)
        tmp_path.replace(self.storage_path)
        os.chmod(self.storage_path, stat.S_IRUSR | stat.S_IWUSR)
        return user

    def unlink(self) -> bool:
        if self.storage_path.exists():
            try:
                self.storage_path.unlink()
                return True
            except Exception:
                return False
        return False

    def is_authorized(self, user_id: int, username: Optional[str] = None) -> bool:
        int_id = int(user_id)
        if int_id in self.env_allowed_ids:
            return True
        if username and username.lstrip("@").lower() in self.env_allowed_usernames:
            paired = self.load_paired_user()
            if paired is None or paired.user_id != int_id:
                self.save_paired_user(user_id=int_id, username=username)
            return True
        paired = self.load_paired_user()
        if paired is not None and (
            paired.user_id == int_id
            or (username and paired.username and paired.username.lower() == username.lstrip("@").lower())
        ):
            return True
        return False

    def get_status(self) -> PairingStatus:
        paired = self.load_paired_user()
        return PairingStatus(
            is_paired=paired is not None,
            paired_user=paired,
            env_allowed_ids=sorted(list(self.env_allowed_ids)),
        )
