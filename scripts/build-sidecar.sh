#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_TRIPLE="${1:-aarch64-apple-darwin}"

echo "==> Building UI..."
cd "$ROOT/ui"
bun install
bun run build

echo "==> Building Python sidecar with PyInstaller..."
cd "$ROOT"
uv run pyinstaller vault-agent.spec --noconfirm --clean

SIDECAR_DIR="$ROOT/dist/vault-agent-sidecar"
if [ ! -d "$SIDECAR_DIR" ]; then
    echo "ERROR: PyInstaller output not found at $SIDECAR_DIR" >&2
    exit 1
fi

echo "==> Copying sidecar to src-tauri/binaries/..."
BINARIES_DIR="$ROOT/src-tauri/binaries"
mkdir -p "$BINARIES_DIR"
rm -rf "$BINARIES_DIR/vault-agent-sidecar-$TARGET_TRIPLE"
cp -R "$SIDECAR_DIR" "$BINARIES_DIR/vault-agent-sidecar-$TARGET_TRIPLE"

echo "==> Done. Sidecar at: $BINARIES_DIR/vault-agent-sidecar-$TARGET_TRIPLE"
echo "    Next: cd src-tauri && cargo tauri build"
