"""Build the self-contained, no-TEMP Pigment installer.

Pipeline:
  1. compile a tiny uninstaller;
  2. compress the portable build into a ZIP payload;
  3. compile a Win32 installer stub with miniz;
  4. append the payload to the stub;
  5. leave only dist/PigmentSetup.exe and dist/SHA256.txt.

The build machine needs MinGW-w64 (g++, gcc, windres). On this machine the
bundled w64devkit is detected automatically.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
PORTABLE = DIST / "PigmentPortable"
PACKAGING = ROOT / "packaging"
MINIZ = PACKAGING / "miniz"
BUILD = ROOT / "build" / "native"
PAYLOAD = BUILD / "PigmentPayload.zip"
STUB = BUILD / "PigmentSetupStub.exe"
UNINSTALLER = BUILD / "PigmentUninstall.exe"
OUTPUT = DIST / "PigmentSetup.exe"
MAGIC = b"PIGMNT01"


def _tool(name: str) -> Path | None:
    found = shutil.which(name)
    if found:
        return Path(found)
    executable = name if name.lower().endswith(".exe") else name + ".exe"
    candidates = [
        ROOT.parent / ".tools" / "w64devkit" / "w64devkit" / "bin" / executable,
        Path("C:/msys64/mingw64/bin") / executable,
        Path("C:/mingw64/bin") / executable,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _run(command: list[str], cwd: Path | None = None) -> None:
    print(">", " ".join(str(part) for part in command))
    local_temp = BUILD / "tmp"
    local_temp.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["TEMP"] = str(local_temp)
    environment["TMP"] = str(local_temp)
    environment["TMPDIR"] = str(local_temp)
    tool_dir = str(Path(command[0]).parent)
    environment["PATH"] = tool_dir + os.pathsep + environment.get("PATH", "")
    subprocess.run(command, cwd=str(cwd or ROOT), check=True, env=environment)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _compile_tools() -> tuple[Path, Path, Path]:
    gcc = _tool("gcc")
    gxx = _tool("g++")
    windres = _tool("windres")
    if not gcc or not gxx or not windres:
        raise RuntimeError(
            "MinGW-w64 toolchain not found. Need gcc, g++ and windres in PATH "
            "or in .tools/w64devkit/w64devkit/bin."
        )
    return gcc, gxx, windres


def _build_payload() -> None:
    if not PORTABLE.exists() or not (PORTABLE / "Pigment.exe").exists():
        raise RuntimeError("Portable build is missing. Run build_exe.py first.")
    if not UNINSTALLER.exists():
        raise RuntimeError("Uninstaller was not compiled.")

    with zipfile.ZipFile(PAYLOAD, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(PORTABLE.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(PORTABLE).as_posix()
            if relative == "README.txt":
                continue
            archive.write(path, relative)
        archive.write(UNINSTALLER, "Uninstall.exe")
        archive.write(ROOT / "LICENSE", "LICENSE.txt")
        archive.write(MINIZ / "LICENSE", "licenses/miniz-LICENSE.txt")
        archive.writestr(
            "README.txt",
            (
                "PIGMENT PAINT 1.0\n"
                "=================\n\n"
                "Запускайте Pigment с ярлыка на Рабочем столе или из меню «Пуск».\n"
                "Не удаляйте и не перемещайте файлы из папки _internal — они нужны приложению.\n\n"
                "Удаление: «Параметры Windows» → «Приложения» → Pigment Paint, или\n"
                "ярлык «Удалить Pigment» в меню «Пуск».\n\n"
                "Python и установка дополнительных компонентов не требуются.\n"
                "Поддерживается Windows 10/11 x64.\n"
            ),
        )


def main() -> int:
    if sys.platform != "win32":
        print("This build script targets Windows.")
        return 1
    if not (ROOT / "assets" / "icon.ico").exists():
        print("Missing assets/icon.ico")
        return 1
    if not PORTABLE.exists():
        print("Portable build is missing. Run build_exe.py first.")
        return 1

    try:
        gcc, gxx, windres = _compile_tools()
    except RuntimeError as exc:
        print(exc)
        return 1

    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)

    # miniz, compiled once as C.
    miniz_objects: list[Path] = []
    for source_name in ("miniz.c", "miniz_tdef.c", "miniz_tinfl.c", "miniz_zip.c"):
        obj = BUILD / (Path(source_name).stem + ".o")
        _run(
            [
                str(gcc),
                "-O2",
                "-I",
                str(MINIZ),
                "-c",
                str(MINIZ / source_name),
                "-o",
                str(obj),
            ]
        )
        miniz_objects.append(obj)

    # Resources and uninstaller.
    _run(
        [
            str(windres),
            "uninstaller.rc",
            "-O",
            "coff",
            "-o",
            str(BUILD / "uninstaller_res.o"),
        ],
        cwd=PACKAGING,
    )
    _run(
        [
            str(gxx),
            "-std=c++17",
            "-O2",
            "-municode",
            "-mwindows",
            "-finput-charset=UTF-8",
            "-fexec-charset=UTF-8",
            "-static-libgcc",
            "-static-libstdc++",
            str(PACKAGING / "uninstaller.cpp"),
            str(BUILD / "uninstaller_res.o"),
            "-o",
            str(UNINSTALLER),
            "-lole32",
            "-lshell32",
            "-lshlwapi",
            "-ladvapi32",
            "-luuid",
            "-luser32",
        ]
    )

    # Resources and installer stub.
    _run(
        [
            str(windres),
            "setup.rc",
            "-O",
            "coff",
            "-o",
            str(BUILD / "setup_res.o"),
        ],
        cwd=PACKAGING,
    )
    _run(
        [
            str(gxx),
            "-std=c++17",
            "-O2",
            "-municode",
            "-mwindows",
            "-finput-charset=UTF-8",
            "-fexec-charset=UTF-8",
            "-static-libgcc",
            "-static-libstdc++",
            "-I",
            str(MINIZ),
            "-I",
            str(PACKAGING),
            str(PACKAGING / "installer.cpp"),
            *[str(obj) for obj in miniz_objects],
            str(BUILD / "setup_res.o"),
            "-o",
            str(STUB),
            "-lcomctl32",
            "-lole32",
            "-lshell32",
            "-lshlwapi",
            "-ladvapi32",
            "-luuid",
            "-luser32",
            "-lgdi32",
        ]
    )

    _build_payload()

    stub_bytes = STUB.read_bytes()
    payload_bytes = PAYLOAD.read_bytes()
    footer = struct.pack("<8sQQ", MAGIC, len(stub_bytes), len(payload_bytes))
    OUTPUT.write_bytes(stub_bytes + payload_bytes + footer)

    exe_hash = _sha256(OUTPUT)
    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    (DIST / "SHA256.txt").write_text(
        (
            f"SHA256 (PigmentSetup.exe) = {exe_hash}\n"
            f"Size = {OUTPUT.stat().st_size} bytes ({size_mb:.1f} MB)\n"
            "Build = native Win32 installer + miniz payload\n"
            "Target = Windows 10/11 x64, per-user installation\n"
            "Runtime = portable onedir (no TEMP extraction)\n"
        ),
        encoding="ascii",
    )

    # Keep the user-facing dist folder minimal.
    for stale in (
        DIST / "PigmentPortable",
        DIST / "PigmentPortable.zip",
    ):
        if stale.is_dir():
            shutil.rmtree(stale, ignore_errors=True)
        elif stale.exists():
            stale.unlink()
    shutil.rmtree(BUILD, ignore_errors=True)

    print(f"Installer: {OUTPUT} ({size_mb:.1f} MB)")
    print(f"SHA256:    {exe_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
