"""
Modal dialogs for Adding/Editing a GitHub Account Profile, Generating SSH Keys,
and Applying an Account or Remote Protocol to a Specific Local Repository.
"""

import os
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable, Optional
import uuid
import webbrowser

from core.models import AccountProfile
from core.switcher import GitSwitcherEngine


# Color Palette (GitHub Dark Dimmed inspired)
BG_MAIN = "#0d1117"
BG_CARD = "#161b22"
BG_INPUT = "#010409"
FG_PRIMARY = "#e6edf3"
FG_MUTED = "#8b949e"
BORDER_COLOR = "#30363d"
ACCENT_BLUE = "#2f81f7"
ACCENT_GREEN = "#238636"
ACCENT_GREEN_HOVER = "#2ea043"
ACCENT_RED = "#da3633"
BTN_SECONDARY = "#21262d"
BTN_SECONDARY_HOVER = "#30363d"

BADGE_COLORS = [
    ("#58a6ff", "Blue"),
    ("#3fb950", "Green"),
    ("#d2a8ff", "Purple"),
    ("#f0883e", "Orange"),
    ("#ff7b72", "Coral"),
    ("#79c0ff", "Cyan"),
]


class AccountDialog(tk.Toplevel):
    """Modal dialog for creating or editing an AccountProfile."""

    def __init__(
        self,
        parent: tk.Widget,
        on_save: Callable[[AccountProfile], None],
        existing: Optional[AccountProfile] = None,
    ):
        super().__init__(parent)
        self.on_save = on_save
        self.existing = existing
        self.title("Edit GitHub Account" if existing else "Add GitHub Account")
        self.configure(bg=BG_MAIN)
        self.geometry("780x880")
        self.minsize(740, 820)
        self.transient(parent)
        self.grab_set()

        try:
            app_root = (
                Path(sys.executable).resolve().parent
                if getattr(sys, "frozen", False)
                else Path(__file__).resolve().parent.parent
            )
            for icon_path in (
                app_root / "assets" / "app_icon.ico",
                Path(getattr(sys, "_MEIPASS", str(app_root))) / "assets" / "app_icon.ico",
            ):
                if icon_path.exists():
                    self.iconbitmap(default=str(icon_path))
                    break
        except Exception:
            pass

        # Variables
        self.var_label = tk.StringVar(value=existing.label if existing else "")
        self.var_git_name = tk.StringVar(value=existing.git_name if existing else "")
        self.var_git_email = tk.StringVar(value=existing.git_email if existing else "")
        self.var_gh_user = tk.StringVar(value=existing.github_username if existing else "")
        self.var_auth_mode = tk.StringVar(value=existing.auth_mode if existing else "both")
        self.var_token = tk.StringVar(value=existing.https_token if existing else "")
        self.var_ssh_path = tk.StringVar(value=existing.ssh_key_path if existing else "")
        self.var_color = tk.StringVar(value=existing.color_tag if existing else "#58a6ff")
        self.show_token = False

        self._build_ui()
        self._center_window(parent)

    def _center_window(self, parent: tk.Widget) -> None:
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.geometry(f"+{x}+{y}")

    def _build_ui(self) -> None:
        container = tk.Frame(self, bg=BG_MAIN, padx=24, pady=18)
        container.pack(fill=tk.BOTH, expand=True)

        title_lbl = tk.Label(
            container,
            text="Edit GitHub Account Profile" if self.existing else "Add New GitHub Account Profile",
            font=("Segoe UI", 14, "bold"),
            bg=BG_MAIN,
            fg=FG_PRIMARY,
            anchor="w",
        )
        title_lbl.pack(fill=tk.X, pady=(0, 12))

        # --- Footer Buttons (Pinned at bottom first so they are ALWAYS visible) ---
        footer = tk.Frame(container, bg=BG_MAIN)
        footer.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 4))

        btn_cancel = tk.Button(
            footer,
            text="Cancel",
            command=self.destroy,
            bg=BTN_SECONDARY,
            fg=FG_PRIMARY,
            activebackground=BTN_SECONDARY_HOVER,
            activeforeground=FG_PRIMARY,
            relief=tk.FLAT,
            font=("Segoe UI", 10),
            padx=18,
            pady=6,
            cursor="hand2",
        )
        btn_cancel.pack(side=tk.RIGHT, padx=(8, 0))

        btn_save = tk.Button(
            footer,
            text="Save Account Profile",
            command=self._save,
            bg=ACCENT_GREEN,
            fg="#ffffff",
            activebackground=ACCENT_GREEN_HOVER,
            activeforeground="#ffffff",
            relief=tk.FLAT,
            font=("Segoe UI", 10, "bold"),
            padx=20,
            pady=6,
            cursor="hand2",
        )
        btn_save.pack(side=tk.RIGHT)

        # --- Section 1: Identity ---
        sec1 = tk.LabelFrame(
            container,
            text="  1. Git Commit & Account Identity  ",
            font=("Segoe UI", 10, "bold"),
            bg=BG_CARD,
            fg=FG_PRIMARY,
            bd=1,
            relief=tk.SOLID,
            padx=14,
            pady=10,
        )
        sec1.pack(fill=tk.X, pady=(0, 12))

        self._add_field(sec1, "Profile Label (e.g., Work, Personal):", self.var_label, row=0)
        self._add_field(sec1, "Git Author Name (user.name):", self.var_git_name, row=1)
        self._add_field(sec1, "Git Author Email (user.email):", self.var_git_email, row=2)
        self._add_field(sec1, "GitHub Username (login handle):", self.var_gh_user, row=3)

        # Color Tag Picker
        color_frame = tk.Frame(sec1, bg=BG_CARD)
        color_frame.grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 2))
        tk.Label(
            color_frame,
            text="Badge Color:",
            font=("Segoe UI", 9),
            bg=BG_CARD,
            fg=FG_MUTED,
        ).pack(side=tk.LEFT, padx=(0, 10))
        for hex_col, col_name in BADGE_COLORS:
            rb = tk.Radiobutton(
                color_frame,
                text=col_name,
                variable=self.var_color,
                value=hex_col,
                bg=BG_CARD,
                fg=hex_col,
                selectcolor=BG_INPUT,
                activebackground=BG_CARD,
                activeforeground=hex_col,
                font=("Segoe UI", 9, "bold"),
            )
            rb.pack(side=tk.LEFT, padx=4)

        # --- Section 2: Authentication Mode ---
        sec2 = tk.LabelFrame(
            container,
            text="  2. Authentication Mode  ",
            font=("Segoe UI", 10, "bold"),
            bg=BG_CARD,
            fg=FG_PRIMARY,
            bd=1,
            relief=tk.SOLID,
            padx=14,
            pady=8,
        )
        sec2.pack(fill=tk.X, pady=(0, 12))

        modes = [
            ("both", "Both (HTTPS Token + SSH Key)"),
            ("https", "HTTPS Only (Personal Access Token)"),
            ("ssh", "SSH Key Only"),
        ]
        for val, text in modes:
            tk.Radiobutton(
                sec2,
                text=text,
                variable=self.var_auth_mode,
                value=val,
                bg=BG_CARD,
                fg=FG_PRIMARY,
                selectcolor=BG_INPUT,
                activebackground=BG_CARD,
                activeforeground=FG_PRIMARY,
                font=("Segoe UI", 9),
            ).pack(side=tk.LEFT, padx=(0, 16))

        # --- Section 3: HTTPS Personal Access Token ---
        sec3 = tk.LabelFrame(
            container,
            text="  3. HTTPS Authentication (Personal Access Token)  ",
            font=("Segoe UI", 10, "bold"),
            bg=BG_CARD,
            fg=FG_PRIMARY,
            bd=1,
            relief=tk.SOLID,
            padx=14,
            pady=10,
        )
        sec3.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            sec3,
            text="GitHub Personal Access Token (encrypted locally with Windows DPAPI):",
            font=("Segoe UI", 9),
            bg=BG_CARD,
            fg=FG_MUTED,
            anchor="w",
        ).pack(fill=tk.X)

        token_row = tk.Frame(sec3, bg=BG_CARD)
        token_row.pack(fill=tk.X, pady=(4, 6))

        self.token_entry = tk.Entry(
            token_row,
            textvariable=self.var_token,
            show="•",
            font=("Consolas", 10),
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            insertbackground=FG_PRIMARY,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            highlightcolor=ACCENT_BLUE,
        )
        self.token_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)

        self.btn_toggle_token = tk.Button(
            token_row,
            text="Show",
            command=self._toggle_token_visibility,
            bg=BTN_SECONDARY,
            fg=FG_PRIMARY,
            activebackground=BTN_SECONDARY_HOVER,
            activeforeground=FG_PRIMARY,
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            padx=10,
            cursor="hand2",
        )
        self.btn_toggle_token.pack(side=tk.LEFT, padx=(6, 0), ipady=2)

        pat_actions = tk.Frame(sec3, bg=BG_CARD)
        pat_actions.pack(fill=tk.X, pady=(2, 0))

        btn_create_pat = tk.Button(
            pat_actions,
            text="Open GitHub Token Settings (Generate PAT in Browser) ↗",
            command=lambda: webbrowser.open("https://github.com/settings/tokens"),
            bg=BG_CARD,
            fg=ACCENT_BLUE,
            activebackground=BG_CARD,
            activeforeground=FG_PRIMARY,
            relief=tk.FLAT,
            font=("Segoe UI", 8, "underline"),
            cursor="hand2",
            anchor="w",
        )
        btn_create_pat.pack(side=tk.LEFT)

        btn_import_gcm = tk.Button(
            pat_actions,
            text="📥 Import Current Token from Credential Manager",
            command=self._import_current_gcm_token,
            bg=BTN_SECONDARY,
            fg=FG_PRIMARY,
            activebackground=BTN_SECONDARY_HOVER,
            activeforeground=FG_PRIMARY,
            relief=tk.FLAT,
            font=("Segoe UI", 8),
            padx=10,
            pady=3,
            cursor="hand2",
        )
        btn_import_gcm.pack(side=tk.RIGHT)

        # --- Section 4: SSH Key ---
        sec4 = tk.LabelFrame(
            container,
            text="  4. SSH Authentication (Private Key)  ",
            font=("Segoe UI", 10, "bold"),
            bg=BG_CARD,
            fg=FG_PRIMARY,
            bd=1,
            relief=tk.SOLID,
            padx=14,
            pady=10,
        )
        sec4.pack(fill=tk.X, pady=(0, 14))

        tk.Label(
            sec4,
            text="Private SSH Key File (e.g. ~/.ssh/id_ed25519_work):",
            font=("Segoe UI", 9),
            bg=BG_CARD,
            fg=FG_MUTED,
            anchor="w",
        ).pack(fill=tk.X)

        ssh_row = tk.Frame(sec4, bg=BG_CARD)
        ssh_row.pack(fill=tk.X, pady=(4, 8))

        ssh_entry = tk.Entry(
            ssh_row,
            textvariable=self.var_ssh_path,
            font=("Consolas", 9),
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            insertbackground=FG_PRIMARY,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            highlightcolor=ACCENT_BLUE,
        )
        ssh_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)

        btn_browse = tk.Button(
            ssh_row,
            text="Browse...",
            command=self._browse_ssh_key,
            bg=BTN_SECONDARY,
            fg=FG_PRIMARY,
            activebackground=BTN_SECONDARY_HOVER,
            activeforeground=FG_PRIMARY,
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            padx=10,
            cursor="hand2",
        )
        btn_browse.pack(side=tk.LEFT, padx=(6, 0), ipady=2)

        ssh_actions = tk.Frame(sec4, bg=BG_CARD)
        ssh_actions.pack(fill=tk.X)

        btn_gen_ssh = tk.Button(
            ssh_actions,
            text="⚡ Generate New Ed25519 SSH Key",
            command=self._generate_new_ssh_key,
            bg=BTN_SECONDARY,
            fg=FG_PRIMARY,
            activebackground=BTN_SECONDARY_HOVER,
            activeforeground=FG_PRIMARY,
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            padx=10,
            pady=4,
            cursor="hand2",
        )
        btn_gen_ssh.pack(side=tk.LEFT, padx=(0, 8))

        btn_copy_pub = tk.Button(
            ssh_actions,
            text="📋 Copy Public Key (.pub)",
            command=self._copy_public_key,
            bg=BTN_SECONDARY,
            fg=FG_PRIMARY,
            activebackground=BTN_SECONDARY_HOVER,
            activeforeground=FG_PRIMARY,
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            padx=10,
            pady=4,
            cursor="hand2",
        )
        btn_copy_pub.pack(side=tk.LEFT, padx=(0, 8))

        btn_gh_ssh = tk.Button(
            ssh_actions,
            text="GitHub SSH Settings ↗",
            command=lambda: webbrowser.open("https://github.com/settings/keys"),
            bg=BG_CARD,
            fg=ACCENT_BLUE,
            activebackground=BG_CARD,
            activeforeground=FG_PRIMARY,
            relief=tk.FLAT,
            font=("Segoe UI", 8, "underline"),
            cursor="hand2",
        )
        btn_gh_ssh.pack(side=tk.LEFT)

    def _add_field(
        self, parent: tk.Widget, label_text: str, var: tk.StringVar, row: int
    ) -> None:
        parent.columnconfigure(1, weight=1)
        lbl = tk.Label(
            parent,
            text=label_text,
            font=("Segoe UI", 9),
            bg=BG_CARD,
            fg=FG_MUTED,
            anchor="w",
        )
        lbl.grid(row=row, column=0, sticky="w", pady=4, padx=(0, 12))

        entry = tk.Entry(
            parent,
            textvariable=var,
            font=("Segoe UI", 10),
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            insertbackground=FG_PRIMARY,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            highlightcolor=ACCENT_BLUE,
        )
        entry.grid(row=row, column=1, sticky="ew", pady=4, ipady=4)

    def _toggle_token_visibility(self) -> None:
        self.show_token = not self.show_token
        self.token_entry.configure(show="" if self.show_token else "•")
        self.btn_toggle_token.configure(text="Hide" if self.show_token else "Show")

    def _import_current_gcm_token(self) -> None:
        user, token = GitSwitcherEngine.read_existing_github_credential(
            self.var_gh_user.get().strip()
        )
        if not token:
            messagebox.showinfo(
                "No Stored GitHub Token Found",
                "No active github.com HTTPS credential was found in Windows Git Credential Manager.",
                parent=self,
            )
            return
        self.var_token.set(token)
        if user and not self.var_gh_user.get().strip():
            self.var_gh_user.set(user)
        messagebox.showinfo(
            "Credential Imported",
            f"Imported stored GitHub credential from Windows Credential Manager (user: {user or 'default'}).",
            parent=self,
        )

    def _browse_ssh_key(self) -> None:
        ssh_dir = Path.home() / ".ssh"
        initial_dir = str(ssh_dir) if ssh_dir.exists() else str(Path.home())
        selected = filedialog.askopenfilename(
            parent=self,
            title="Select Private SSH Key File",
            initialdir=initial_dir,
        )
        if selected:
            if selected.endswith(".pub"):
                maybe_priv = selected[:-4]
                if os.path.exists(maybe_priv):
                    selected = maybe_priv
                else:
                    messagebox.showwarning(
                        "Public Key Selected",
                        "You selected a .pub file. Please select the PRIVATE key file (without .pub).",
                        parent=self,
                    )
            self.var_ssh_path.set(Path(selected).as_posix())

    def _generate_new_ssh_key(self) -> None:
        tag = (
            self.var_gh_user.get().strip()
            or self.var_label.get().strip()
            or "github"
        )
        email = self.var_git_email.get().strip() or tag
        ok, key_path_or_err, pub_key = GitSwitcherEngine.generate_ssh_key(
            email=email, filename_tag=tag
        )
        if not ok:
            messagebox.showerror("SSH Key Generation Failed", key_path_or_err, parent=self)
            return

        self.var_ssh_path.set(key_path_or_err)
        if pub_key:
            self.clipboard_clear()
            self.clipboard_append(pub_key)
            messagebox.showinfo(
                "SSH Key Generated & Copied",
                f"Created new Ed25519 SSH key:\n{key_path_or_err}\n\n"
                f"Your PUBLIC key (.pub) has been automatically copied to your clipboard!\n"
                f"Paste it into GitHub -> Settings -> SSH and GPG keys.",
                parent=self,
            )

    def _copy_public_key(self) -> None:
        priv_path = self.var_ssh_path.get().strip()
        if not priv_path:
            messagebox.showwarning(
                "No SSH Key Configured",
                "Please select or generate an SSH key first.",
                parent=self,
            )
            return
        pub_key = GitSwitcherEngine.read_public_key(priv_path)
        if not pub_key:
            messagebox.showerror(
                "Public Key Not Found",
                f"Could not read or derive a public key from:\n{priv_path}",
                parent=self,
            )
            return
        self.clipboard_clear()
        self.clipboard_append(pub_key)
        messagebox.showinfo(
            "Public Key Copied",
            f"Public key copied to clipboard:\n\n{pub_key}\n\n"
            f"You can now paste it into https://github.com/settings/keys",
            parent=self,
        )

    def _save(self) -> None:
        label = self.var_label.get().strip()
        git_name = self.var_git_name.get().strip()
        git_email = self.var_git_email.get().strip()
        gh_user = self.var_gh_user.get().strip()

        if not label:
            messagebox.showwarning("Missing Label", "Please enter a Profile Label (e.g. Work or Personal).", parent=self)
            return
        if not git_name or not git_email:
            messagebox.showwarning(
                "Missing Git Identity",
                "Please enter both Git Author Name (user.name) and Git Author Email (user.email) so commits are properly attributed.",
                parent=self,
            )
            return

        profile = AccountProfile(
            id=self.existing.id if self.existing else str(uuid.uuid4()),
            label=label,
            git_name=git_name,
            git_email=git_email,
            github_username=gh_user or git_name,
            auth_mode=self.var_auth_mode.get(),
            https_token=self.var_token.get().strip(),
            ssh_key_path=self.var_ssh_path.get().strip(),
            color_tag=self.var_color.get(),
        )
        self.on_save(profile)
        self.destroy()
