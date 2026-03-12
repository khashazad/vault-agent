# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for vault-agent sidecar (one-folder mode)."""

from pathlib import Path

ROOT = Path(SPECPATH)
UI_DIST = ROOT / "ui" / "dist"

ui_datas = [
    (str(f), str(f.relative_to(ROOT).parent))
    for f in UI_DIST.rglob("*")
    if f.is_file()
] if UI_DIST.exists() else []

a = Analysis(
    ["src/__main__.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=ui_datas,
    hiddenimports=[
        # uvicorn internals
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # app modules
        "src",
        "src.server",
        "src.config",
        "src.store",
        "src.models",
        "src.vault",
        "src.vault.reader",
        "src.vault.writer",
        "src.agent",
        "src.agent.agent",
        "src.agent.tools",
        "src.agent.prompts",
        "src.agent.changeset",
        "src.agent.diff",
        "src.agent.wikify",
        "src.rag",
        "src.rag.chunker",
        "src.rag.embedder",
        "src.rag.store",
        "src.rag.indexer",
        "src.rag.search",
        "src.zotero",
        "src.zotero.client",
        "src.zotero.sync",
        "src.zotero.orchestrator",
        "src.zotero.background",
        # third-party that pyinstaller misses
        "anthropic",
        "pydantic_core",
        "pyzotero",
        "feedparser",
        "frontmatter",
        "dotenv",
        "voyageai",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "test",
        "unittest",
        "pytest",
    ],
    noarchive=False,
    optimize=0,
)

# NOTE: if pyarrow/lancedb fail to bundle, uncomment:
# from PyInstaller.utils.hooks import collect_all
# a.datas += collect_all("pyarrow")[0]
# a.datas += collect_all("lancedb")[0]

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="vault-agent-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="vault-agent-sidecar",
)
