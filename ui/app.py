"""
Main Desktop GUI Window for GitHub Account Switcher.
Provides:
- Active Global Git Identity & Auth banner
- Profile Cards with one-click "Switch Active Account" (Global), "Apply to Local Repo",
  "Verify Connection (HTTPS & SSH)", "Copy SSH PubKey", "Edit", and "Delete"
- Built-in Activity & Verification Log Drawer
- Quick Import of current global Git identity on first launch
"""

import ctypes
from datetime import datetime
from pathlib import Path
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional
import uuid

from core.models import AccountProfile, ProfileStore
from core.switcher import GitSwitcherEngine
from ui.dialogs import (
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_GREEN_HOVER,
    ACCENT_RED,
    BG_CARD,
    BG_INPUT,
    BG_MAIN,
    BORDER_COLOR,
    BTN_SECONDARY,
    BTN_SECONDARY_HOVER,
    FG_MUTED,
    FG_PRIMARY,
    AccountDialog,
)


class GitHubSwitcherApp(tk.Tk):
    """Main application window for GitHub Account Switcher."""

    def __init__(self, base_dir: Optional[Path] = None):
        super().__init__()
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent
        self.store = ProfileStore(self.base_dir)

        self.title("GitHub Account Switcher — Global & Repo Auth Manager (HTTPS + SSH)")
        self.geometry("980x740")
        self.minsize(860, 620)
        self.configure(bg=BG_MAIN)

        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("HadyKh.GitHubAccountSwitcher.1.0")
        except Exception:
            pass

        try:
            icon_candidates = [
                self.base_dir / "assets" / "app_icon.ico",
                Path(getattr(sys, "_MEIPASS", str(self.base_dir))) / "assets" / "app_icon.ico",
            ]
            for icon_path in icon_candidates:
                if icon_path.exists():
                    self.iconbitmap(default=str(icon_path))
                    break
        except Exception:
            pass

        self._ensure_initial_import()
        self._build_layout()
        self.refresh_ui()

    def _ensure_initial_import(self) -> None:
        """If no accounts exist yet, offer or auto-import the current global Git config."""
        if self.store.accounts:
            return
        current = GitSwitcherEngine.get_current_git_identity()
        name = current.get("user.name", "").strip()
        email = current.get("user.email", "").strip()
        if name or email:
            # Check if default SSH key exists
            ssh_dir = Path.home() / ".ssh"
            default_ssh = ""
            for candidate in ("id_ed25519", "id_rsa"):
                p = ssh_dir / candidate
                if p.is_file():
                    default_ssh = p.as_posix()
                    break

            # Also check if there is already a saved GitHub HTTPS credential in Windows Credential Manager
            existing_gh_user, existing_gh_token = GitSwitcherEngine.read_existing_github_credential()

            imported = AccountProfile(
                id=str(uuid.uuid4()),
                label="Current Account (Imported)",
                git_name=name or "GitHub User",
                git_email=email or "user@example.com",
                github_username=(
                    existing_gh_user
                    or current.get("github.username")
                    or (email.split("@")[0] if email else "github-user")
                ),
                auth_mode="both",
                https_token=existing_gh_token,
                ssh_key_path=default_ssh,
                color_tag="#58a6ff",
            )
            self.store.accounts.append(imported)
            self.store.active_account_id = imported.id
            self.store.save()

    def _build_layout(self) -> None:
        # --- Top Header Bar ---
        header = tk.Frame(self, bg=BG_CARD, padx=22, pady=14, highlightthickness=1, highlightbackground=BORDER_COLOR)
        header.pack(fill=tk.X)

        title_col = tk.Frame(header, bg=BG_CARD)
        title_col.pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(
            title_col,
            text="🐙 GitHub Account Switcher",
            font=("Segoe UI", 16, "bold"),
            bg=BG_CARD,
            fg=FG_PRIMARY,
            anchor="w",
        ).pack(anchor="w")

        tk.Label(
            title_col,
            text="Switch Git Commit Author, Windows HTTPS Credential Manager PAT, and SSH Keys in one click",
            font=("Segoe UI", 9),
            bg=BG_CARD,
            fg=FG_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        actions_col = tk.Frame(header, bg=BG_CARD)
        actions_col.pack(side=tk.RIGHT)

        btn_repo_tool = tk.Button(
            actions_col,
            text="📁 Convert Repo Remote (HTTPS ↔ SSH)",
            command=self._convert_repo_protocol_prompt,
            bg=BTN_SECONDARY,
            fg=FG_PRIMARY,
            activebackground=BTN_SECONDARY_HOVER,
            activeforeground=FG_PRIMARY,
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            padx=12,
            pady=6,
            cursor="hand2",
        )
        btn_repo_tool.pack(side=tk.LEFT, padx=(0, 10))

        btn_add = tk.Button(
            actions_col,
            text="＋ Add GitHub Account",
            command=self._open_add_dialog,
            bg=ACCENT_GREEN,
            fg="#ffffff",
            activebackground=ACCENT_GREEN_HOVER,
            activeforeground="#ffffff",
            relief=tk.FLAT,
            font=("Segoe UI", 10, "bold"),
            padx=16,
            pady=6,
            cursor="hand2",
        )
        btn_add.pack(side=tk.LEFT)

        # --- Live Global Git Status Banner ---
        self.status_banner = tk.Frame(
            self,
            bg="#111927",
            padx=22,
            pady=10,
            highlightthickness=1,
            highlightbackground="#1f6feb",
        )
        self.status_banner.pack(fill=tk.X, padx=20, pady=(14, 10))

        self.lbl_live_status = tk.Label(
            self.status_banner,
            text="Loading current global Git configuration...",
            font=("Consolas", 10),
            bg="#111927",
            fg="#79c0ff",
            justify=tk.LEFT,
            anchor="w",
        )
        self.lbl_live_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_refresh = tk.Button(
            self.status_banner,
            text="↻ Refresh Status",
            command=self.refresh_ui,
            bg=BTN_SECONDARY,
            fg=FG_PRIMARY,
            activebackground=BTN_SECONDARY_HOVER,
            activeforeground=FG_PRIMARY,
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            padx=10,
            pady=3,
            cursor="hand2",
        )
        btn_refresh.pack(side=tk.RIGHT)

        # --- Main Scrollable Account Cards Area ---
        cards_outer = tk.Frame(self, bg=BG_MAIN, padx=20)
        cards_outer.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(cards_outer, bg=BG_MAIN, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(cards_outer, orient=tk.VERTICAL, command=self.canvas.yview)
        self.cards_container = tk.Frame(self.canvas, bg=BG_MAIN)

        self.cards_container.bind("<Configure>", self._update_scrollregion)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.cards_container, anchor="nw")
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bind mousewheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # --- Bottom Activity & Verification Log Console ---
        log_frame = tk.LabelFrame(
            self,
            text="  Activity & Verification Log  ",
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=FG_MUTED,
            bd=1,
            relief=tk.SOLID,
            padx=10,
            pady=6,
        )
        log_frame.pack(fill=tk.X, padx=20, pady=(8, 16))

        self.log_text = tk.Text(
            log_frame,
            height=6,
            bg=BG_INPUT,
            fg="#c9d1d9",
            font=("Consolas", 9),
            relief=tk.FLAT,
            wrap=tk.WORD,
            state=tk.DISABLED,
        )
        self.log_text.pack(fill=tk.X, expand=True)

        self.log("GitHub Account Switcher ready. Select an account below to switch global or repo credentials.")

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        self._update_scrollregion()

    def _update_scrollregion(self, event: Optional[tk.Event] = None) -> None:
        self.update_idletasks()
        canvas_h = self.canvas.winfo_height()
        content_h = self.cards_container.winfo_reqheight()
        content_w = self.canvas.winfo_width()

        if content_h > canvas_h and canvas_h > 10:
            self.canvas.configure(scrollregion=(0, 0, content_w, content_h))
            if not self.scrollbar.winfo_ismapped():
                self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        else:
            self.canvas.configure(scrollregion=(0, 0, content_w, canvas_h))
            self.canvas.yview_moveto(0.0)
            if self.scrollbar.winfo_ismapped():
                self.scrollbar.pack_forget()

    def _on_mousewheel(self, event: tk.Event) -> None:
        try:
            if self.cards_container.winfo_reqheight() <= self.canvas.winfo_height():
                return
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def refresh_ui(self) -> None:
        """Refreshes the live status banner and rebuilds the account cards."""
        live = GitSwitcherEngine.get_current_git_identity()
        live_name = live.get("user.name") or "(unset)"
        live_email = live.get("user.email") or "(unset)"
        live_user = live.get("github.username") or "(default)"
        live_ssh = live.get("core.sshCommand") or "(default ~/.ssh/config)"

        active_profile = self.store.get_by_id(self.store.active_account_id)
        active_label = active_profile.label if active_profile else "Unmatched / Custom"

        status_text = (
            f"ACTIVE GLOBAL GIT IDENTITY : {active_label}  |  Author: {live_name} <{live_email}>\n"
            f"HTTPS Username: {live_user}  |  SSH Command: {live_ssh}"
        )
        self.lbl_live_status.configure(text=status_text)

        # Clear existing card widgets
        for child in self.cards_container.winfo_children():
            child.destroy()

        if not self.store.accounts:
            empty_lbl = tk.Label(
                self.cards_container,
                text="No GitHub accounts added yet.\nClick '＋ Add GitHub Account' in the top right to create your first profile.",
                font=("Segoe UI", 11),
                bg=BG_MAIN,
                fg=FG_MUTED,
                pady=40,
            )
            empty_lbl.pack(fill=tk.X)
            return

        for profile in self.store.accounts:
            is_active = (
                profile.id == self.store.active_account_id
                or (
                    profile.git_email.lower() == live_email.lower()
                    and profile.git_name.lower() == live_name.lower()
                )
            )
            self._create_account_card(profile, is_active)

        self._update_scrollregion()

    def _create_account_card(self, profile: AccountProfile, is_active: bool) -> None:
        border_col = "#2ea043" if is_active else BORDER_COLOR
        border_thickness = 2 if is_active else 1

        card = tk.Frame(
            self.cards_container,
            bg=BG_CARD,
            padx=18,
            pady=14,
            highlightthickness=border_thickness,
            highlightbackground=border_col,
        )
        card.pack(fill=tk.X, pady=6)

        # Top Row: Color Strip + Label + Active Badge + Action Buttons
        top_row = tk.Frame(card, bg=BG_CARD)
        top_row.pack(fill=tk.X)

        color_dot = tk.Label(
            top_row,
            text="●",
            font=("Segoe UI", 14),
            bg=BG_CARD,
            fg=profile.color_tag,
        )
        color_dot.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(
            top_row,
            text=profile.label,
            font=("Segoe UI", 13, "bold"),
            bg=BG_CARD,
            fg=FG_PRIMARY,
        ).pack(side=tk.LEFT)

        tk.Label(
            top_row,
            text=f"(@{profile.github_username})" if profile.github_username else "",
            font=("Consolas", 10),
            bg=BG_CARD,
            fg=FG_MUTED,
        ).pack(side=tk.LEFT, padx=(8, 10))

        if is_active:
            active_badge = tk.Label(
                top_row,
                text=" ✓ ACTIVE GLOBAL ACCOUNT ",
                font=("Segoe UI", 8, "bold"),
                bg="#238636",
                fg="#ffffff",
                padx=6,
                pady=2,
            )
            active_badge.pack(side=tk.LEFT, padx=4)

        # Mode Badge
        mode_badge_text = f" MODE: {profile.auth_mode.upper()} "
        tk.Label(
            top_row,
            text=mode_badge_text,
            font=("Consolas", 8, "bold"),
            bg="#21262d",
            fg="#79c0ff",
            padx=6,
            pady=2,
        ).pack(side=tk.LEFT, padx=6)

        # Primary Switch Button on right
        if is_active:
            btn_switch = tk.Button(
                top_row,
                text="↻ Re-Apply Global Auth",
                command=lambda p=profile: self._switch_to_profile(p),
                bg=BTN_SECONDARY,
                fg="#3fb950",
                activebackground=BTN_SECONDARY_HOVER,
                activeforeground="#3fb950",
                relief=tk.FLAT,
                font=("Segoe UI", 9, "bold"),
                padx=14,
                pady=5,
                cursor="hand2",
            )
        else:
            btn_switch = tk.Button(
                top_row,
                text="⚡ Switch to This Account",
                command=lambda p=profile: self._switch_to_profile(p),
                bg=ACCENT_BLUE,
                fg="#ffffff",
                activebackground="#388bfd",
                activeforeground="#ffffff",
                relief=tk.FLAT,
                font=("Segoe UI", 9, "bold"),
                padx=16,
                pady=5,
                cursor="hand2",
            )
        btn_switch.pack(side=tk.RIGHT)

        # Middle Row: Details (Commit Author, HTTPS Status, SSH Key Status)
        details_frame = tk.Frame(card, bg=BG_CARD, pady=8)
        details_frame.pack(fill=tk.X)

        author_str = f"Commit Author : {profile.git_name} <{profile.git_email}>"
        https_status = (
            "Configured (DPAPI Encrypted PAT)"
            if profile.https_token
            else "Not set"
        )
        if profile.ssh_key_path:
            ssh_status = (
                f"{profile.ssh_key_path} (Ready)"
                if profile.ssh_key_exists
                else f"{profile.ssh_key_path} (FILE MISSING!)"
            )
        else:
            ssh_status = "Not set"

        tk.Label(
            details_frame,
            text=f"{author_str}\nHTTPS Token   : {https_status}    |    SSH Private Key : {ssh_status}",
            font=("Consolas", 9),
            bg=BG_CARD,
            fg=FG_MUTED,
            justify=tk.LEFT,
            anchor="w",
        ).pack(side=tk.LEFT)

        # Bottom Row: Utility Actions
        bottom_row = tk.Frame(card, bg=BG_CARD)
        bottom_row.pack(fill=tk.X, pady=(4, 0))

        self._make_card_btn(
            bottom_row,
            "🔍 Test & Verify Auth (HTTPS / SSH)",
            lambda p=profile: self._verify_profile(p),
        ).pack(side=tk.LEFT, padx=(0, 8))

        self._make_card_btn(
            bottom_row,
            "📂 Apply to Specific Local Repo...",
            lambda p=profile: self._apply_to_local_repo(p),
        ).pack(side=tk.LEFT, padx=(0, 8))

        if profile.ssh_key_path:
            self._make_card_btn(
                bottom_row,
                "📋 Copy SSH Public Key",
                lambda p=profile: self._copy_profile_pubkey(p),
            ).pack(side=tk.LEFT, padx=(0, 8))

        self._make_card_btn(
            bottom_row,
            "🗑 Delete",
            lambda p=profile: self._delete_profile(p),
            fg_color="#ff7b72",
        ).pack(side=tk.RIGHT)

        self._make_card_btn(
            bottom_row,
            "✏ Edit Profile",
            lambda p=profile: self._open_edit_dialog(p),
        ).pack(side=tk.RIGHT, padx=(0, 8))

    def _make_card_btn(
        self,
        parent: tk.Widget,
        text: str,
        command,
        fg_color: str = FG_PRIMARY,
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=BTN_SECONDARY,
            fg=fg_color,
            activebackground=BTN_SECONDARY_HOVER,
            activeforeground=fg_color,
            relief=tk.FLAT,
            font=("Segoe UI", 8),
            padx=10,
            pady=4,
            cursor="hand2",
        )

    def _switch_to_profile(self, profile: AccountProfile) -> None:
        self.log(f"Switching active global GitHub account to '{profile.label}' (@{profile.github_username})...")
        ok, messages = GitSwitcherEngine.apply_profile(profile)
        for msg in messages:
            self.log(f"  {msg}")

        self.store.active_account_id = profile.id
        self.store.save()
        self.refresh_ui()

        if ok:
            self.log(f"✓ Successfully activated '{profile.label}'. All new commits, clones, and pushes will use this account.")
        else:
            self.log(f"⚠ Switched to '{profile.label}' with warnings (check messages above).")

    def _apply_to_local_repo(self, profile: AccountProfile) -> None:
        folder = filedialog.askdirectory(
            parent=self,
            title=f"Select Local Git Repository to Bind to '{profile.label}'",
        )
        if not folder:
            return
        git_dir = Path(folder) / ".git"
        if not git_dir.exists():
            messagebox.showerror(
                "Not a Git Repository",
                f"The selected folder does not contain a .git directory:\n{folder}",
                parent=self,
            )
            return

        ok, messages = GitSwitcherEngine.apply_profile(profile, repo_path=folder)
        for msg in messages:
            self.log(f"  {msg}")
        if ok:
            messagebox.showinfo(
                "Applied to Local Repository",
                f"Successfully bound repository:\n{folder}\n\nto profile '{profile.label}' ({profile.git_name} <{profile.git_email}>).",
                parent=self,
            )

    def _verify_profile(self, profile: AccountProfile) -> None:
        self.log(f"Verifying credentials for '{profile.label}' (@{profile.github_username})...")

        def worker():
            results = []
            if profile.auth_mode in ("https", "both"):
                _, https_msg = GitSwitcherEngine.verify_https_token(profile.https_token)
                results.append(https_msg)
            if profile.auth_mode in ("ssh", "both"):
                _, ssh_msg = GitSwitcherEngine.verify_ssh_key(profile.ssh_key_path)
                results.append(ssh_msg)

            def report():
                for line in results:
                    self.log(f"  [{profile.label}] {line}")
                messagebox.showinfo(
                    f"Verification Results — {profile.label}",
                    "\n\n".join(results) if results else "No authentication credentials configured.",
                    parent=self,
                )

            self.after(0, report)

        threading.Thread(target=worker, daemon=True).start()

    def _copy_profile_pubkey(self, profile: AccountProfile) -> None:
        pub = GitSwitcherEngine.read_public_key(profile.ssh_key_path)
        if not pub:
            messagebox.showerror(
                "Public Key Not Found",
                f"Could not find or derive public key for:\n{profile.ssh_key_path}",
                parent=self,
            )
            return
        self.clipboard_clear()
        self.clipboard_append(pub)
        self.log(f"Copied SSH public key for '{profile.label}' to clipboard.")
        messagebox.showinfo(
            "SSH Public Key Copied",
            f"Public key copied to clipboard:\n\n{pub}",
            parent=self,
        )

    def _open_add_dialog(self) -> None:
        def on_saved(new_profile: AccountProfile):
            self.store.add_or_update(new_profile)
            self.log(f"Added new profile '{new_profile.label}' (@{new_profile.github_username}).")
            if len(self.store.accounts) == 1:
                self._switch_to_profile(new_profile)
            else:
                self.refresh_ui()

        AccountDialog(self, on_save=on_saved, existing=None)

    def _open_edit_dialog(self, profile: AccountProfile) -> None:
        def on_saved(updated_profile: AccountProfile):
            self.store.add_or_update(updated_profile)
            self.log(f"Updated profile '{updated_profile.label}'.")
            if self.store.active_account_id == updated_profile.id:
                self._switch_to_profile(updated_profile)
            else:
                self.refresh_ui()

        AccountDialog(self, on_save=on_saved, existing=profile)

    def _delete_profile(self, profile: AccountProfile) -> None:
        confirm = messagebox.askyesno(
            "Delete Account Profile",
            f"Are you sure you want to remove '{profile.label}' (@{profile.github_username}) from the switcher?\n\n"
            f"(Your SSH key files on disk will NOT be deleted.)",
            parent=self,
        )
        if not confirm:
            return
        self.store.delete(profile.id)
        self.log(f"Deleted profile '{profile.label}'.")
        self.refresh_ui()

    def _convert_repo_protocol_prompt(self) -> None:
        folder = filedialog.askdirectory(
            parent=self,
            title="Select Local Git Repository to Convert Origin Remote URL (HTTPS <-> SSH)",
        )
        if not folder:
            return

        win = tk.Toplevel(self)
        win.title("Convert Repository Remote Protocol")
        win.configure(bg=BG_MAIN, padx=20, pady=18)
        win.geometry("460x200")
        win.transient(self)
        win.grab_set()

        tk.Label(
            win,
            text=f"Repository: {folder}",
            font=("Consolas", 9),
            bg=BG_MAIN,
            fg=FG_MUTED,
            wraplength=420,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 12))

        tk.Label(
            win,
            text="Convert 'origin' remote URL to:",
            font=("Segoe UI", 10, "bold"),
            bg=BG_MAIN,
            fg=FG_PRIMARY,
        ).pack(anchor="w", pady=(0, 10))

        btn_row = tk.Frame(win, bg=BG_MAIN)
        btn_row.pack(fill=tk.X)

        def do_convert(proto: str):
            ok, msg = GitSwitcherEngine.convert_repo_remote(folder, proto)
            self.log(f"[Repo Converter] {msg}")
            win.destroy()
            if ok:
                messagebox.showinfo("Remote URL Updated", msg, parent=self)
            else:
                messagebox.showerror("Remote Conversion Failed", msg, parent=self)

        tk.Button(
            btn_row,
            text="🔒 Switch Origin to HTTPS",
            command=lambda: do_convert("https"),
            bg=ACCENT_BLUE,
            fg="#ffffff",
            relief=tk.FLAT,
            font=("Segoe UI", 9, "bold"),
            padx=14,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_row,
            text="🔑 Switch Origin to SSH (git@github.com)",
            command=lambda: do_convert("ssh"),
            bg=ACCENT_GREEN,
            fg="#ffffff",
            relief=tk.FLAT,
            font=("Segoe UI", 9, "bold"),
            padx=14,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.LEFT)
