"""Python code ko alag temp folder mein timeout ke saath chalana.

NOTE: Ye asli sandbox nahi hai (sirf alag folder + timeout). Untrusted code ke liye
Docker use karo. Abhi ke liye apne hi likhwaye hue code ke liye theek hai.
"""
import os
import subprocess
import sys
import tempfile

from config import CODE_TIMEOUT_SECONDS


def run_python(code: str):
    """Returns (ok: bool, output: str)"""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "main.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            p = subprocess.run(
                [sys.executable, path],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=CODE_TIMEOUT_SECONDS,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            return False, f"Timeout: code {CODE_TIMEOUT_SECONDS}s se zyada chala."
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode == 0, out.strip()[-3000:]
