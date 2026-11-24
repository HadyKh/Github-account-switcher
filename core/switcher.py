"""
Core switching engine for GitHub Account Switcher.
Handles:
1. Global & Local Git author configuration (user.name, user.email)
2. HTTPS Personal Access Token (PAT) injection into Git Credential Manager / Windows Credential Manager
3. SSH Key generation, ~/.ssh/config management, and git core.sshCommand setup
4. Live verification against GitHub REST API (HTTPS) and ssh -T git@github.com (SSH)
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple
import urllib.error
import urllib.request

from core.models import AccountProfile

# Prevent console window popups on Windows when running subprocesses from GUI
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

SSH_BLOCK_START = "# >>> GITHUB_ACCOUNT_SWITCHER_START >>>"
SSH_BLOCK_END = "# <<< GITHUB_ACCOUNT_SWITCHER_END <<<"


def _run_cmd(
    args: List[str],
    input_text: Optional[str] = None,
    cwd: Optional[str] = None,
    timeout: int = 15,
) -> Tuple[int, str, str]:
    """Run a command silently and return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            args,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return -1, "", str(exc)


class GitSwitcherEngine:
    """Executes all system-level Git, Credential Manager, and SSH operations."""

    @staticmethod
    def read_existing_github_credential(username: str = "") -> Tuple[str, str]:
        """
        Reads the currently stored GitHub HTTPS username & token/password from
        Git Credential Manager (if one exists) using `git credential fill`.
        Does NOT prompt interactively because GCM_INTERACTIVE=never and GIT_TERMINAL_PROMPT=0.
        Returns (username, password_or_token).
        """
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GCM_INTERACTIVE"] = "never"
        payload = "protocol=https\nhost=github.com\n"
        if username:
            payload += f"username={username}\n"
        payload += "\n"
        try:
            proc = subprocess.run(
                ["git", "credential", "fill"],
                input=payload,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=8,
                creationflags=CREATE_NO_WINDOW,
            )
            if proc.returncode != 0:
                return "", ""
            found_user = ""
            found_pass = ""
            for line in proc.stdout.splitlines():
                if line.startswith("username="):
                    found_user = line.split("=", 1)[1].strip()
                elif line.startswith("password="):
                    found_pass = line.split("=", 1)[1].strip()
            return found_user, found_pass
        except Exception:
            return "", ""

    @staticmethod
    def backup_file_once(file_path: Path, backup_dir: Path) -> Optional[Path]:
        """Creates a one-time .original.bak backup of a system config file before modifying it."""
        try:
            if not file_path.exists():
                return None
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_target = backup_dir / f"{file_path.name}.original.bak"
            if not backup_target.exists():
                backup_target.write_bytes(file_path.read_bytes())
                return backup_target
        except Exception:
            pass
        return None

    @staticmethod
    def get_current_git_identity(repo_path: Optional[str] = None) -> Dict[str, str]:
        """Reads current global (or local repo) git identity and SSH config."""
        scope_flag = ["--local"] if repo_path else ["--global"]
        cwd = repo_path if repo_path else None

        _, name, _ = _run_cmd(["git", "config", *scope_flag, "user.name"], cwd=cwd)
        _, email, _ = _run_cmd(["git", "config", *scope_flag, "user.email"], cwd=cwd)
        _, ssh_cmd, _ = _run_cmd(["git", "config", *scope_flag, "core.sshCommand"], cwd=cwd)
        _, gh_user, _ = _run_cmd(
            ["git", "config", *scope_flag, "credential.https://github.com.username"],
            cwd=cwd,
        )

        return {
            "user.name": name,
            "user.email": email,
            "core.sshCommand": ssh_cmd,
            "github.username": gh_user,
        }

    @classmethod
    def apply_profile(
        cls,
        profile: AccountProfile,
        repo_path: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Switches the active GitHub account globally (or for a specific local repository).
        Returns (success, log_messages).
        """
        logs: List[str] = []
        overall_ok = True
        scope_label = f"Repository ({repo_path})" if repo_path else "Global"
        scope_flag = ["--local"] if repo_path else ["--global"]
        cwd = repo_path if repo_path else None

        # Create one-time safety backups of ~/.gitconfig and ~/.ssh/config before first global switch
        if not repo_path:
            app_root = (
                Path(sys.executable).resolve().parent
                if getattr(sys, "frozen", False)
                else Path(__file__).resolve().parent.parent
            )
            backup_dir = app_root / "data" / "backups"
            bak_git = cls.backup_file_once(Path.home() / ".gitconfig", backup_dir)
            if bak_git:
                logs.append(f"[Safety Backup] Backed up original .gitconfig -> {bak_git}")
            bak_ssh = cls.backup_file_once(Path.home() / ".ssh" / "config", backup_dir)
            if bak_ssh:
                logs.append(f"[Safety Backup] Backed up original ~/.ssh/config -> {bak_ssh}")

        # 1. Set Git Commit Author (user.name & user.email)
        if profile.git_name:
            code, _, err = _run_cmd(
                ["git", "config", *scope_flag, "user.name", profile.git_name], cwd=cwd
            )
            if code == 0:
                logs.append(f"[{scope_label}] Set git user.name = '{profile.git_name}'")
            else:
                overall_ok = False
                logs.append(f"[{scope_label}] ERROR setting user.name: {err}")

        if profile.git_email:
            code, _, err = _run_cmd(
                ["git", "config", *scope_flag, "user.email", profile.git_email], cwd=cwd
            )
            if code == 0:
                logs.append(f"[{scope_label}] Set git user.email = '{profile.git_email}'")
            else:
                overall_ok = False
                logs.append(f"[{scope_label}] ERROR setting user.email: {err}")

        # 2. Configure HTTPS Credentials (PAT)
        if profile.auth_mode in ("https", "both"):
            if profile.github_username:
                _run_cmd(
                    [
                        "git",
                        "config",
                        *scope_flag,
                        "credential.https://github.com.username",
                        profile.github_username,
                    ],
                    cwd=cwd,
                )
                logs.append(
                    f"[{scope_label}] Set github.com HTTPS username = '{profile.github_username}'"
                )

            if profile.https_token and not repo_path:
                ok_cred, cred_msg = cls.update_https_credential(
                    username=profile.github_username or profile.git_name or "git",
                    token=profile.https_token,
                )
                logs.append(cred_msg)
                if not ok_cred:
                    overall_ok = False
            elif profile.auth_mode == "https" and not profile.https_token:
                logs.append(
                    "[HTTPS] Note: No Personal Access Token saved for this profile; skipped Credential Manager update."
                )

        # 3. Configure SSH Key
        if profile.auth_mode in ("ssh", "both") and profile.ssh_key_path:
            key_path = Path(os.path.expanduser(profile.ssh_key_path)).resolve()
            posix_key_path = key_path.as_posix()
            if not key_path.exists():
                overall_ok = False
                logs.append(f"[SSH] ERROR: Private key file not found at '{posix_key_path}'")
            else:
                # Set git core.sshCommand so all git clone/push/fetch commands use this key
                ssh_command = (
                    f'ssh -i "{posix_key_path}" -o IdentitiesOnly=yes'
                )
                code, _, err = _run_cmd(
                    ["git", "config", *scope_flag, "core.sshCommand", ssh_command],
                    cwd=cwd,
                )
                if code == 0:
                    logs.append(f"[{scope_label}] Set core.sshCommand -> '{posix_key_path}'")
                else:
                    overall_ok = False
                    logs.append(f"[{scope_label}] ERROR setting core.sshCommand: {err}")

                # Also update ~/.ssh/config if applying globally
                if not repo_path:
                    ok_ssh, ssh_msg = cls.update_ssh_config(posix_key_path, profile.label)
                    logs.append(ssh_msg)
                    if not ok_ssh:
                        overall_ok = False
        elif profile.auth_mode == "https":
            # Clear custom core.sshCommand if user switched to an HTTPS-only profile
            _run_cmd(["git", "config", *scope_flag, "--unset", "core.sshCommand"], cwd=cwd)
            if not repo_path:
                cls.remove_managed_ssh_config()
            logs.append(f"[{scope_label}] Cleared custom SSH key override (HTTPS-only profile).")

        # 4. Optional: If GitHub CLI (gh) is installed and logged into this user, switch it too
        if not repo_path and profile.github_username:
            code, _, _ = _run_cmd(["gh", "auth", "switch", "-u", profile.github_username])
            if code == 0:
                logs.append(f"[GitHub CLI] Switched active 'gh' CLI account to '{profile.github_username}'.")

        return overall_ok, logs

    @classmethod
    def update_https_credential(cls, username: str, token: str) -> Tuple[bool, str]:
        """
        Replaces the active GitHub HTTPS credential in Git Credential Manager (Windows Credential Store).
        First erases any cached github.com credentials, then stores the new username + PAT.
        """
        # 1. Erase existing credentials via git credential reject
        reject_payload = "protocol=https\nhost=github.com\n\n"
        _run_cmd(["git", "credential", "reject"], input_text=reject_payload)
        if username:
            reject_user_payload = f"protocol=https\nhost=github.com\nusername={username}\n\n"
            _run_cmd(["git", "credential", "reject"], input_text=reject_user_payload)

        # 2. Approve / Store the new credential via git credential approve
        approve_payload = (
            f"protocol=https\n"
            f"host=github.com\n"
            f"username={username}\n"
            f"password={token}\n\n"
        )
        code, _, err = _run_cmd(["git", "credential", "approve"], input_text=approve_payload)

        if code == 0:
            return (
                True,
                f"[HTTPS] Stored PAT for '{username}' in Windows Git Credential Manager.",
            )
        return (
            False,
            f"[HTTPS] ERROR updating Git Credential Manager: {err or 'exit code ' + str(code)}",
        )

    @classmethod
    def update_ssh_config(cls, posix_key_path: str, label: str = "") -> Tuple[bool, str]:
        """
        Updates ~/.ssh/config with a managed Host github.com block pointing to posix_key_path.
        Preserves all other entries in ~/.ssh/config.
        """
        try:
            ssh_dir = Path.home() / ".ssh"
            ssh_dir.mkdir(parents=True, exist_ok=True)
            config_path = ssh_dir / "config"

            existing = ""
            if config_path.exists():
                existing = config_path.read_text(encoding="utf-8", errors="replace")

            managed_block = (
                f"{SSH_BLOCK_START}\n"
                f"# Active Profile: {label}\n"
                f"Host github.com\n"
                f"    HostName github.com\n"
                f"    User git\n"
                f'    IdentityFile "{posix_key_path}"\n'
                f"    IdentitiesOnly yes\n"
                f"{SSH_BLOCK_END}\n"
            )

            pattern = re.compile(
                re.escape(SSH_BLOCK_START) + r".*?" + re.escape(SSH_BLOCK_END) + r"\n?",
                re.DOTALL,
            )

            if pattern.search(existing):
                updated = pattern.sub(managed_block, existing)
            else:
                # Prepend at the top of ~/.ssh/config so OpenSSH matches it first
                updated = managed_block + ("\n" + existing.lstrip() if existing.strip() else "")

            config_path.write_text(updated, encoding="utf-8")
            return True, f"[SSH] Updated ~/.ssh/config (Host github.com -> {posix_key_path})"
        except Exception as exc:
            return False, f"[SSH] ERROR updating ~/.ssh/config: {exc}"

    @classmethod
    def remove_managed_ssh_config(cls) -> None:
        """Removes the managed block from ~/.ssh/config if present."""
        try:
            config_path = Path.home() / ".ssh" / "config"
            if not config_path.exists():
                return
            existing = config_path.read_text(encoding="utf-8", errors="replace")
            pattern = re.compile(
                re.escape(SSH_BLOCK_START) + r".*?" + re.escape(SSH_BLOCK_END) + r"\n?",
                re.DOTALL,
            )
            if pattern.search(existing):
                updated = pattern.sub("", existing).lstrip()
                config_path.write_text(updated, encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def generate_ssh_key(
        email: str,
        filename_tag: str,
    ) -> Tuple[bool, str, str]:
        """
        Generates a new Ed25519 SSH key pair in ~/.ssh/id_ed25519_<tag> with no passphrase.
        Returns (success, private_key_path_or_error, public_key_content).
        """
        safe_tag = re.sub(r"[^a-zA-Z0-9_-]", "_", filename_tag.strip().lower()) or "github"
        ssh_dir = Path.home() / ".ssh"
        ssh_dir.mkdir(parents=True, exist_ok=True)
        key_path = ssh_dir / f"id_ed25519_{safe_tag}"

        # If key already exists, append a numeric suffix
        counter = 1
        base_key_path = key_path
        while key_path.exists():
            key_path = ssh_dir / f"{base_key_path.name}_{counter}"
            counter += 1

        code, out, err = _run_cmd(
            [
                "ssh-keygen",
                "-t",
                "ed25519",
                "-C",
                email or safe_tag,
                "-f",
                str(key_path),
                "-N",
                "",
            ]
        )
        if code != 0:
            return False, f"ssh-keygen failed: {err or out}", ""

        pub_path = Path(str(key_path) + ".pub")
        pub_content = ""
        if pub_path.exists():
            pub_content = pub_path.read_text(encoding="utf-8", errors="replace").strip()

        return True, key_path.as_posix(), pub_content

    @staticmethod
    def read_public_key(private_key_path: str) -> str:
        """Reads the corresponding .pub file for a given private key path."""
        if not private_key_path:
            return ""
        expanded = Path(os.path.expanduser(private_key_path))
        pub_path = (
            expanded
            if expanded.suffix == ".pub"
            else Path(str(expanded) + ".pub")
        )
        if pub_path.is_file():
            return pub_path.read_text(encoding="utf-8", errors="replace").strip()
        # Fallback: derive public key using ssh-keygen -y
        if expanded.is_file():
            code, out, _ = _run_cmd(["ssh-keygen", "-y", "-f", str(expanded)])
            if code == 0 and out:
                return out
        return ""

    @staticmethod
    def verify_https_token(token: str) -> Tuple[bool, str]:
        """Tests a GitHub Personal Access Token against https://api.github.com/user."""
        if not token:
            return False, "HTTPS: No Personal Access Token configured."
        req = urllib.request.Request(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "GitHub-Account-Switcher",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                login = data.get("login", "unknown")
                name = data.get("name") or ""
                scopes = resp.headers.get("X-OAuth-Scopes", "fine-grained / none listed")
                name_part = f" ({name})" if name else ""
                return (
                    True,
                    f"HTTPS Authenticated as @{login}{name_part} | Scopes: {scopes}",
                )
        except urllib.error.HTTPError as e:
            return False, f"HTTPS Verification Failed: HTTP {e.code} ({e.reason})"
        except Exception as e:
            return False, f"HTTPS Verification Error: {e}"

    @staticmethod
    def verify_ssh_key(private_key_path: str) -> Tuple[bool, str]:
        """Tests an SSH private key against git@github.com."""
        if not private_key_path:
            return False, "SSH: No private key path configured."
        expanded = Path(os.path.expanduser(private_key_path))
        if not expanded.is_file():
            return False, f"SSH: Key file does not exist ({expanded})"

        code, out, err = _run_cmd(
            [
                "ssh",
                "-T",
                "git@github.com",
                "-i",
                expanded.as_posix(),
                "-o",
                "IdentitiesOnly=yes",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=10",
            ],
            timeout=15,
        )
        combined = f"{out}\n{err}".strip()
        # GitHub returns exit code 1 with message: "Hi <username>! You've successfully authenticated, but GitHub does not provide shell access."
        if "successfully authenticated" in combined.lower():
            return True, f"SSH Verified: {combined}"
        return False, f"SSH Verification Failed (exit {code}): {combined}"

    @staticmethod
    def convert_repo_remote(repo_path: str, target_protocol: str) -> Tuple[bool, str]:
        """
        Converts a local repository's 'origin' remote URL between HTTPS and SSH.
        target_protocol: 'https' or 'ssh'
        """
        code, current_url, err = _run_cmd(
            ["git", "remote", "get-url", "origin"], cwd=repo_path
        )
        if code != 0 or not current_url:
            return False, f"Could not read 'origin' remote in {repo_path}: {err}"

        # Match github.com owner/repo from either HTTPS or SSH URL
        m_https = re.match(r"https?://(?:[^@]+@)?github\.com/([^/]+)/(.+?)(?:\.git)?$", current_url)
        m_ssh = re.match(r"(?:git@|ssh://git@)github\.com[:/]([^/]+)/(.+?)(?:\.git)?$", current_url)
        match = m_https or m_ssh
        if not match:
            return False, f"Origin URL '{current_url}' is not a standard github.com URL."

        owner, repo = match.group(1), match.group(2)
        if target_protocol == "ssh":
            new_url = f"git@github.com:{owner}/{repo}.git"
        else:
            new_url = f"https://github.com/{owner}/{repo}.git"

        if new_url == current_url:
            return True, f"Origin is already using {target_protocol.upper()} ({current_url})."

        code, _, err = _run_cmd(
            ["git", "remote", "set-url", "origin", new_url], cwd=repo_path
        )
        if code == 0:
            return True, f"Converted origin URL: {current_url} -> {new_url}"
        return False, f"Failed to update origin URL: {err}"
