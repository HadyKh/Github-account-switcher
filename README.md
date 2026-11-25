# GitHub Account Switcher (Desktop GUI + CLI)

A lightweight, zero-dependency Windows Desktop application to manage and switch between multiple GitHub accounts seamlessly across your entire machine.

When you select an account and click **⚡ Switch to This Account**, every **commit**, **clone**, **pull**, and **push** across all terminals, IDEs, and VS Code will use that account automatically:

1. **Git Commit Author Identity**:
   - Updates `git config --global user.name`
   - Updates `git config --global user.email`
2. **HTTPS Authentication (Personal Access Token)**:
   - Encrypts your GitHub Personal Access Tokens at rest using **Windows DPAPI** (`CryptProtectData`), tied strictly to your Windows login.
   - Automatically clears the old `github.com` credential and injects the selected account's PAT into **Git Credential Manager / Windows Credential Manager** (`git credential reject` + `git credential approve`) and sets `credential.https://github.com.username`.
3. **SSH Key Authentication**:
   - Can generate new `ed25519` SSH keys (`ssh-keygen`) per account directly from the GUI and copy the `.pub` key to your clipboard with one click.
   - Updates `git config --global core.sshCommand` to explicitly use the active profile's private key (`ssh -i "<path>" -o IdentitiesOnly=yes`).
   - Updates a managed block in `~/.ssh/config` for `Host github.com` without touching any of your other SSH hosts.
4. **Per-Repository Binding & Remote Converter**:
   - **Apply to Specific Local Repo**: Bind a specific local Git repository (`--local`) to a chosen account without changing your global default.
   - **Convert Repo Remote (`HTTPS ↔ SSH`)**: Switch any local repository's `origin` remote URL between `https://github.com/owner/repo.git` and `git@github.com:owner/repo.git` in one click.
5. **Live Verification**:
   - Click **🔍 Test & Verify Auth (HTTPS / SSH)** on any card to test both the HTTPS token against `https://api.github.com/user` and the SSH key against `ssh -T git@github.com`.

---

## How to Launch

### Option 1: Double-click the Desktop Launcher
Double-click [`run_switcher.bat`](file:///D:/Scripts/Github-account-switcher/run_switcher.bat) in Windows Explorer. It launches the GUI cleanly in the background using `pythonw` (no command prompt window behind it).

### Option 2: Run via Python
```powershell
python main.py
```

### Option 3: Build Standalone `.exe`
Run [`build_exe.bat`](file:///D:/Scripts/Github-account-switcher/build_exe.bat) to package the application into a standalone `GitHubAccountSwitcher.exe` using PyInstaller.

### Option 4: Quick Command-Line Switching (Optional)
You can also inspect status or switch accounts directly from PowerShell or CMD:
```powershell
# Show current active global Git identity & SSH/HTTPS config
python main.py --status

# List all configured profiles
python main.py --list

# Switch active account by label, GitHub username, or email
python main.py --switch "Work"
```

---

## Project Structure

- [`main.py`](file:///D:/Scripts/Github-account-switcher/main.py) — Entry point (High-DPI Desktop GUI + CLI flags)
- [`run_switcher.bat`](file:///D:/Scripts/Github-account-switcher/run_switcher.bat) — One-click Windows launcher
- [`build_exe.bat`](file:///D:/Scripts/Github-account-switcher/build_exe.bat) — Standalone `.exe` build script
- [`core/security.py`](file:///D:/Scripts/Github-account-switcher/core/security.py) — Windows DPAPI (`Crypt32.dll`) token encryption & decryption
- [`core/models.py`](file:///D:/Scripts/Github-account-switcher/core/models.py) — `AccountProfile` and `ProfileStore` (`data/accounts.json`)
- [`core/switcher.py`](file:///D:/Scripts/Github-account-switcher/core/switcher.py) — Git config, Git Credential Manager, `~/.ssh/config`, `ssh-keygen`, and GitHub verification engine
- [`ui/app.py`](file:///D:/Scripts/Github-account-switcher/ui/app.py) — Main dark-mode Desktop GUI window
- [`ui/dialogs.py`](file:///D:/Scripts/Github-account-switcher/ui/dialogs.py) — Add/Edit Account modal with built-in SSH Key generator & PAT manager
