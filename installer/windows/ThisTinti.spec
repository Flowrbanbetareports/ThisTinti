# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = Path(SPECPATH).resolve().parents[1]


def source_snapshot() -> list[tuple[str, str]]:
    excluded_parts = {
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".runtime",
        "build",
        "dist",
        "release",
        ".coverage",
    }
    excluded_suffixes = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3"}
    items: list[tuple[str, str]] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if (
            any(part in excluded_parts for part in relative.parts)
            or path.name.startswith(".coverage")
            or path.suffix.lower() in excluded_suffixes
        ):
            continue
        destination = Path("source") / relative.parent
        items.append((str(path), str(destination)))
    return items


datas = [
    (str(ROOT / "app" / "static"), "app/static"),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "NOTICE"), "."),
    (str(ROOT / "PRIVACY.md"), "."),
    (str(ROOT / "TERMS_OF_USE.md"), "."),
    (str(ROOT / "DISCLAIMER.md"), "."),
    (str(ROOT / "TRADEMARKS.md"), "."),
    (str(ROOT / "SUPPORT.md"), "."),
    (str(ROOT / "docs" / "THIRD_PARTY_NOTICES.md"), "docs"),
    (str(ROOT / "docs" / "LOCAL_EDITION.md"), "docs"),
]
datas += collect_data_files("pypdfium2")
datas += source_snapshot()

binaries = collect_dynamic_libs("pypdfium2")
hiddenimports = (
    collect_submodules("pypdfium2")
    + [
        # Uvicorn receives this module as a string ("app.main:app"), so
        # PyInstaller cannot discover it through normal static analysis.
        "app.main",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.protocols.websockets.websockets_sansio_impl",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        "email_validator",
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.dialects.sqlite.pysqlite",
    ]
)

analysis = Analysis(
    [str(ROOT / "run_thistinti.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(ROOT / "installer" / "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "coverage",
        "ruff",
        "bandit",
        "pip_audit",
        "pygments",
        "alembic",
        "mako",
        "IPython",
        "jupyter",
        "matplotlib",
        "numpy",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="ThisTinti",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "installer" / "assets" / "thistinti.ico"),
    version=None,
)

collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ThisTinti",
)
