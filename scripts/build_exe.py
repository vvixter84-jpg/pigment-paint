"""Build a reliable portable Windows distribution with PyInstaller.

A one-file build extracts Python and Qt into %TEMP% on every launch.  Some
locked-down machines forbid that, producing "Could not create temporary
directory".  The portable folder below keeps every dependency next to the EXE,
so no extraction is needed.

Usage:
    .venv\\Scripts\\python.exe scripts\\build_exe.py
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
ICON = ASSETS / "icon.ico"
VERSION_FILE = ROOT / "packaging" / "version_info.txt"
PORTABLE_NAME = "PigmentPortable"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    if sys.platform != "win32":
        print("This build script targets Windows.")
        return 1
    if not ICON.exists():
        print(f"Missing icon: {ICON}")
        return 1
    if not VERSION_FILE.exists():
        print(f"Missing version file: {VERSION_FILE}")
        return 1

    from PyInstaller.__main__ import run as pyinstaller_run

    if BUILD.exists():
        shutil.rmtree(BUILD, ignore_errors=True)
    # Remove stale products from the previous (one-file / old portable) build.
    for stale in (
        DIST / "Pigment.exe",
        DIST / "Pigment",
        DIST / PORTABLE_NAME,
        DIST / f"{PORTABLE_NAME}.zip",
    ):
        if stale.is_dir():
            shutil.rmtree(stale, ignore_errors=True)
        elif stale.exists():
            stale.unlink()

    arguments = [
        str(ROOT / "main.py"),
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "Pigment",
        "--icon",
        str(ICON),
        "--add-data",
        f"{ASSETS};assets",
        "--version-file",
        str(VERSION_FILE),
        "--paths",
        str(ROOT),
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD),
        "--specpath",
        str(BUILD),
        "--exclude-module",
        "pytest",
        "--exclude-module",
        "PyQt6.QtTest",
    ]
    pyinstaller_run(arguments)

    built = DIST / "Pigment"
    executable = built / "Pigment.exe"
    if not executable.exists():
        print("Build finished without Pigment.exe.")
        return 2

    portable = DIST / PORTABLE_NAME
    built.rename(portable)
    executable = portable / "Pigment.exe"

    readme = (
        "PIGMENT PAINT 1.0\n"
        "=================\n\n"
        "Служебная папка portable-сборки. Для обычной установки используйте\n"
        "PigmentSetup.exe: он сам скопирует эти файлы в LocalAppData и создаст\n"
        "ярлык Pigment на Рабочем столе и в меню «Пуск».\n\n"
        "Python и установка дополнительных компонентов не требуются.\n"
        "Поддерживается Windows 10/11 x64.\n\n"
        f"SHA-256 Pigment.exe: {_sha256(executable)}\n"
    )
    (portable / "README.txt").write_text(readme, encoding="utf-8-sig")

    print(f"Portable staging folder: {portable}")
    print(f"Executable:              {executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
