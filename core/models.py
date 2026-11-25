"""
Data models and JSON persistence for GitHub account profiles.
Automatically encrypts PAT tokens on disk using Windows DPAPI.
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from typing import List, Optional
import uuid

from core.security import decrypt_secret, encrypt_secret


@dataclass
class AccountProfile:
    id: str
    label: str                  # e.g., "Work", "Personal"
    git_name: str               # git config user.name
    git_email: str              # git config user.email
    github_username: str        # GitHub login handle (e.g., "octocat")
    auth_mode: str = "both"     # "https", "ssh", or "both"
    https_token: str = ""       # In-memory decrypted GitHub PAT
    ssh_key_path: str = ""      # Path to private SSH key (e.g., C:/Users/.../.ssh/id_ed25519_work)
    preferred_protocol: str = "https"  # "https" or "ssh" (optional reference)
    color_tag: str = "#58a6ff"  # UI accent badge color

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "git_name": self.git_name,
            "git_email": self.git_email,
            "github_username": self.github_username,
            "auth_mode": self.auth_mode,
            "https_token_encrypted": encrypt_secret(self.https_token) if self.https_token else "",
            "ssh_key_path": self.ssh_key_path,
            "preferred_protocol": self.preferred_protocol,
            "color_tag": self.color_tag,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AccountProfile":
        enc_token = data.get("https_token_encrypted", "")
        plain_token = decrypt_secret(enc_token) if enc_token else data.get("https_token", "")
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            label=data.get("label", "Unnamed Account"),
            git_name=data.get("git_name", ""),
            git_email=data.get("git_email", ""),
            github_username=data.get("github_username", ""),
            auth_mode=data.get("auth_mode", "both"),
            https_token=plain_token,
            ssh_key_path=data.get("ssh_key_path", ""),
            preferred_protocol=data.get("preferred_protocol", "https"),
            color_tag=data.get("color_tag", "#58a6ff"),
        )

    @property
    def has_https(self) -> bool:
        return bool(self.https_token and self.auth_mode in ("https", "both"))

    @property
    def has_ssh(self) -> bool:
        return bool(self.ssh_key_path and self.auth_mode in ("ssh", "both"))

    @property
    def ssh_key_exists(self) -> bool:
        if not self.ssh_key_path:
            return False
        return Path(os.path.expanduser(self.ssh_key_path)).is_file()


class ProfileStore:
    """Manages loading and saving AccountProfiles to data/accounts.json."""

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            if getattr(sys, "frozen", False):
                exe_dir = Path(sys.executable).resolve().parent
                if (exe_dir / "data").exists() and os.access(exe_dir / "data", os.W_OK):
                    base_dir = exe_dir
                else:
                    local_app_data = os.environ.get("LOCALAPPDATA")
                    base_dir = (
                        Path(local_app_data) / "GitHubAccountSwitcher"
                        if local_app_data
                        else exe_dir
                    )
            else:
                base_dir = Path(__file__).resolve().parent.parent
        self.data_dir = base_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.data_dir / "accounts.json"
        self.accounts: List[AccountProfile] = []
        self.active_account_id: Optional[str] = None
        self.load()

    def load(self) -> None:
        if not self.file_path.exists():
            self.accounts = []
            self.active_account_id = None
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.active_account_id = raw.get("active_account_id")
            self.accounts = [
                AccountProfile.from_dict(item) for item in raw.get("accounts", [])
            ]
        except Exception:
            self.accounts = []
            self.active_account_id = None

    def save(self) -> None:
        payload = {
            "active_account_id": self.active_account_id,
            "accounts": [acc.to_dict() for acc in self.accounts],
        }
        temp_path = self.file_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        temp_path.replace(self.file_path)

    def get_by_id(self, account_id: Optional[str]) -> Optional[AccountProfile]:
        if not account_id:
            return None
        for acc in self.accounts:
            if acc.id == account_id:
                return acc
        return None

    def add_or_update(self, profile: AccountProfile) -> None:
        for idx, existing in enumerate(self.accounts):
            if existing.id == profile.id:
                self.accounts[idx] = profile
                self.save()
                return
        self.accounts.append(profile)
        self.save()

    def delete(self, account_id: str) -> None:
        self.accounts = [acc for acc in self.accounts if acc.id != account_id]
        if self.active_account_id == account_id:
            self.active_account_id = None
        self.save()
