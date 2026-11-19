# GitHub Account Switcher

A lightweight Windows utility to manage and switch between multiple GitHub accounts (Git commit author identity, Windows Credential Manager HTTPS tokens, and SSH keys).

## Architecture Overview

- `core/` — Backend logic for Windows DPAPI encryption, profile persistence, and Git/SSH/GCM credential switching.
- `ui/` — Desktop GUI built with Tkinter.
- `main.py` — Entry point.
