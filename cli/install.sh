#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────
# Looma CLI — 一键安装脚本
#
# Usage:
#   ./install.sh                 安装到 looma 后端 venv
#   ./install.sh --standalone    独立安装到 ~/.looma/venv
# ────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_VENV="$SCRIPT_DIR/../backend/venv"
STANDALONE_VENV="$HOME/.looma/venv"
BIN_LINK="/usr/local/bin/looma"
STANDALONE=false

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${CYAN}  ➜${NC} $1"; }
ok()    { echo -e "${GREEN}  ✅${NC} $1"; }
warn()  { echo -e "${YELLOW}  ⚠${NC}  $1"; }
err()   { echo -e "${RED}  ❌${NC} $1"; }

# Parse args
for arg in "$@"; do
    case "$arg" in
        --standalone) STANDALONE=true ;;
    esac
done

echo ""
echo -e "${CYAN}🛸  Looma CLI Installer v1.0.0${NC}"
echo -e "${CYAN}   职业成长平台的运维大脑${NC}"
echo ""

# ── Determine Python / venv ──
if [ "$STANDALONE" = false ] && [ -f "$BACKEND_VENV/bin/python" ]; then
    VENV_DIR="$BACKEND_VENV"
    PYTHON="$VENV_DIR/bin/python"
    PIP="$VENV_DIR/bin/pip"
    ok "Using looma backend venv: $VENV_DIR"
elif [ "$STANDALONE" = true ]; then
    # Check system Python
    PYTHON=""
    for candidate in python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" &>/dev/null; then
            ver=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
                PYTHON="$candidate"
                break
            fi
        fi
    done
    if [ -z "$PYTHON" ]; then
        err "Python >= 3.10 required."
        exit 1
    fi
    VENV_DIR="$STANDALONE_VENV"
    if [ ! -d "$VENV_DIR" ]; then
        info "Creating standalone venv at $VENV_DIR ..."
        $PYTHON -m venv "$VENV_DIR"
    fi
    PIP="$VENV_DIR/bin/pip"
    ok "Standalone venv: $VENV_DIR"
else
    err "Backend venv not found at $BACKEND_VENV"
    echo "    Run './install.sh --standalone' for standalone install."
    exit 1
fi

# ── Install looma-cli ──
info "Installing looma-cli ..."
"$PIP" install -q --upgrade pip 2>/dev/null || true
"$PIP" install -q -e "$SCRIPT_DIR"
ok "Package installed"

# ── Create symlink ──
LOOMA_BIN="$VENV_DIR/bin/looma"
if [ -L "$BIN_LINK" ] || [ -f "$BIN_LINK" ]; then
    info "Removing existing symlink at $BIN_LINK ..."
    sudo rm -f "$BIN_LINK" 2>/dev/null || rm -f "$BIN_LINK" 2>/dev/null || true
fi

if [ -w "$(dirname "$BIN_LINK")" ]; then
    ln -sf "$LOOMA_BIN" "$BIN_LINK"
    ok "Symlink: $BIN_LINK → $LOOMA_BIN"
else
    warn "Cannot write to /usr/local/bin. Adding alias ..."
    for rc in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile"; do
        if [ -f "$rc" ]; then
            if ! grep -q "alias looma=" "$rc" 2>/dev/null; then
                echo "alias looma='$LOOMA_BIN'" >> "$rc"
                ok "Alias added to $rc"
            fi
        fi
    done
    echo ""
    warn "Please restart your shell or run: source ~/.zshrc"
fi

# ── Verify ──
echo ""
if "$LOOMA_BIN" --version &>/dev/null; then
    ok "Installation complete!"
    echo ""
    echo -e "  ${CYAN}Quick start:${NC}"
    echo "    looma --help"
    echo "    looma doctor"
    echo "    looma status"
    echo "    looma credit 腾讯"
    echo ""
    echo -e "  ${CYAN}Tip:${NC} Run 'looma doctor' to check system health."
else
    err "Verification failed."
fi
