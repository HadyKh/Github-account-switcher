"""
GitHub Account Switcher — Entry Point
Supports:
- Desktop GUI (default when launched with no arguments)
- Quick CLI switching:
    python main.py --list
    python main.py --status
    python main.py --switch "<Profile Label or GitHub Username>"
"""

import argparse
import ctypes
import os
from pathlib import Path
import sys

if getattr(sys, "frozen", False):
    _exe_dir = Path(sys.executable).resolve().parent
    if (_exe_dir / "data").exists() and os.access(_exe_dir / "data", os.W_OK):
        BASE_DIR = _exe_dir
    else:
        _local_app_data = os.environ.get("LOCALAPPDATA")
        BASE_DIR = (
            Path(_local_app_data) / "GitHubAccountSwitcher"
            if _local_app_data
            else _exe_dir
        )
else:
    BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.models import ProfileStore
from core.switcher import GitSwitcherEngine


def enable_dpi_awareness() -> None:
    """Enables High-DPI awareness on Windows for crisp fonts in Tkinter."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def run_cli(args: argparse.Namespace) -> int:
    store = ProfileStore(BASE_DIR)

    if args.status:
        live = GitSwitcherEngine.get_current_git_identity()
        print("=== Active Global Git Identity ===")
        print(f"  user.name        : {live.get('user.name') or '(unset)'}")
        print(f"  user.email       : {live.get('user.email') or '(unset)'}")
        print(f"  github.username  : {live.get('github.username') or '(default)'}")
        print(f"  core.sshCommand  : {live.get('core.sshCommand') or '(default ~/.ssh/config)'}")
        return 0

    if args.list:
        if not store.accounts:
            print("No GitHub account profiles saved yet. Launch the GUI to add accounts.")
            return 0
        print("=== Saved GitHub Account Profiles ===")
        for acc in store.accounts:
            marker = "* [ACTIVE]" if acc.id == store.active_account_id else "  "
            print(
                f"{marker} {acc.label} (@{acc.github_username}) | {acc.git_name} <{acc.git_email}> | mode={acc.auth_mode}"
            )
        return 0

    if args.switch:
        query = args.switch.strip().lower()
        target = None
        for acc in store.accounts:
            if (
                acc.label.lower() == query
                or acc.github_username.lower() == query
                or acc.git_email.lower() == query
            ):
                target = acc
                break
        if not target:
            print(f"Error: No profile matching '{args.switch}' found.")
            return 1

        ok, logs = GitSwitcherEngine.apply_profile(target)
        for line in logs:
            print(line)
        store.active_account_id = target.id
        store.save()
        return 0 if ok else 1

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GitHub Account Switcher (Desktop GUI + CLI)"
    )
    parser.add_argument("--list", action="store_true", help="List saved GitHub profiles")
    parser.add_argument("--status", action="store_true", help="Show active global Git identity")
    parser.add_argument(
        "--switch",
        metavar="ACCOUNT",
        help="Switch active global account by label, username, or email",
    )
    args = parser.parse_args()

    if args.list or args.status or args.switch:
        sys.exit(run_cli(args))

    enable_dpi_awareness()
    from ui.app import GitHubSwitcherApp

    app = GitHubSwitcherApp(base_dir=BASE_DIR)
    app.mainloop()


if __name__ == "__main__":
    main()
