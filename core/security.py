"""
DPAPI encryption helper for Windows.
Encrypts and decrypts secrets (such as GitHub Personal Access Tokens) tied to the current Windows user account.
Zero external dependencies (uses ctypes + Windows Crypt32.dll).
"""

import base64
import ctypes
from ctypes import wintypes


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


_crypt32 = ctypes.windll.crypt32
_kernel32 = ctypes.windll.kernel32

_CryptProtectData = _crypt32.CryptProtectData
_CryptProtectData.argtypes = [
    ctypes.POINTER(DATA_BLOB),
    wintypes.LPCWSTR,
    ctypes.POINTER(DATA_BLOB),
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(DATA_BLOB),
]
_CryptProtectData.restype = wintypes.BOOL

_CryptUnprotectData = _crypt32.CryptUnprotectData
_CryptUnprotectData.argtypes = [
    ctypes.POINTER(DATA_BLOB),
    ctypes.POINTER(wintypes.LPWSTR),
    ctypes.POINTER(DATA_BLOB),
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(DATA_BLOB),
]
_CryptUnprotectData.restype = wintypes.BOOL

_LocalFree = _kernel32.LocalFree
_LocalFree.argtypes = [ctypes.c_void_p]
_LocalFree.restype = ctypes.c_void_p

CRYPTPROTECT_UI_FORBIDDEN = 0x01


def encrypt_secret(plain_text: str) -> str:
    """Encrypts a plaintext string using Windows DPAPI and returns a base64-encoded string."""
    if not plain_text:
        return ""
    try:
        raw_bytes = plain_text.encode("utf-8")
        buffer = ctypes.create_string_buffer(raw_bytes, len(raw_bytes))
        in_blob = DATA_BLOB(len(raw_bytes), buffer)
        out_blob = DATA_BLOB()

        if not _CryptProtectData(
            ctypes.byref(in_blob),
            "GitHubAccountSwitcher",
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        ):
            # Fallback to base64 obfuscation if DPAPI fails in restricted context
            return "b64:" + base64.b64encode(raw_bytes).decode("ascii")

        try:
            encrypted_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return "dpapi:" + base64.b64encode(encrypted_bytes).decode("ascii")
        finally:
            _LocalFree(out_blob.pbData)
    except Exception:
        return "b64:" + base64.b64encode(plain_text.encode("utf-8")).decode("ascii")


def decrypt_secret(cipher_text: str) -> str:
    """Decrypts a DPAPI base64-encoded string back into plaintext."""
    if not cipher_text:
        return ""
    try:
        if cipher_text.startswith("b64:"):
            return base64.b64decode(cipher_text[4:]).decode("utf-8")
        if cipher_text.startswith("dpapi:"):
            raw_cipher = base64.b64decode(cipher_text[6:])
        else:
            raw_cipher = base64.b64decode(cipher_text)

        buffer = ctypes.create_string_buffer(raw_cipher, len(raw_cipher))
        in_blob = DATA_BLOB(len(raw_cipher), buffer)
        out_blob = DATA_BLOB()

        if not _CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        ):
            return ""

        try:
            decrypted_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return decrypted_bytes.decode("utf-8")
        finally:
            _LocalFree(out_blob.pbData)
    except Exception:
        return ""
