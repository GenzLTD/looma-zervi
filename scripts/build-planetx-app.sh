#!/usr/bin/env bash
# ============================================================================
# PlanetX App 一体化构建脚本
#
# 用途：先构建 PlanetX 前端，再启动带前端服务的 Flask 后端。
# 结果：一个进程 (Flask :5200) 同时提供 API + PlanetX SPA。
#
# 用法：
#   ./scripts/build-planetx-app.sh            # 构建 + 启动后端
#   ./scripts/build-planetx-app.sh --build-only  # 仅构建前端，不启动
#   ./scripts/build-planetx-app.sh --run-only    # 跳过构建，直接启动
#
# 环境变量：
#   PLANETX_DIST_DIR     前端产物目录（默认 ../frontend/packages/planetx/dist）
#   FLASK_ENV            Flask 环境（默认 development）
#   FLASK_PORT           后端端口（默认 5200）
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

PLANETX_DIST_DIR="${PLANETX_DIST_DIR:-$PROJECT_ROOT/frontend/packages/planetx/dist}"
FLASK_ENV="${FLASK_ENV:-development}"
FLASK_PORT="${FLASK_PORT:-5200}"

BUILD_ONLY=false
RUN_ONLY=false

for arg in "$@"; do
  case "$arg" in
    --build-only) BUILD_ONLY=true ;;
    --run-only)   RUN_ONLY=true ;;
    *)            echo "Unknown arg: $arg"; exit 1 ;;
  esac
done

echo "============================================"
echo " PlanetX App - 一体化构建"
echo "============================================"
echo " 前端目录:   $PROJECT_ROOT/frontend"
echo " 产物目录:   $PLANETX_DIST_DIR"
echo " 后端目录:   $PROJECT_ROOT/backend"
echo " FLASK_ENV:  $FLASK_ENV"
echo " FLASK_PORT: $FLASK_PORT"
echo "============================================"

# --- Step 1: Build PlanetX frontend ---
if [ "$RUN_ONLY" != true ]; then
  echo ""
  echo "[1/2] 构建 PlanetX 前端..."

  cd "$PROJECT_ROOT/frontend"

  # Ensure shared-core is built first (shared dependency)
  echo "  → 构建 shared-core..."
  pnpm --filter @looma/shared-core build

  echo "  → 构建 PlanetX (VITE_API_BASE=\"\" = same-origin)..."
  VITE_API_BASE="" pnpm --filter @looma/planetx build

  if [ ! -f "$PLANETX_DIST_DIR/index.html" ]; then
    echo "ERROR: PlanetX dist/index.html not found after build!"
    exit 1
  fi

  echo "  ✅ PlanetX 构建完成 ($PLANETX_DIST_DIR)"
else
  echo ""
  echo "[1/2] 跳过构建 (--run-only)"
fi

# --- Step 2: Start backend with PlanetX SPA ---
if [ "$BUILD_ONLY" != true ]; then
  echo ""
  echo "[2/2] 启动后端 (Flask :$FLASK_PORT)..."

  cd "$PROJECT_ROOT/backend"

  export PLANETX_DIST_DIR="$PLANETX_DIST_DIR"
  export FLASK_ENV="$FLASK_ENV"
  export FLASK_PORT="$FLASK_PORT"

  echo "  PLANETX_DIST_DIR=$PLANETX_DIST_DIR"
  echo "  FLASK_ENV=$FLASK_ENV"
  echo "  FLASK_PORT=$FLASK_PORT"
  echo ""
  echo "  🌐 PlanetX SPA:   http://localhost:$FLASK_PORT"
  echo "  📡 API endpoint:  http://localhost:$FLASK_PORT/v1/..."
  echo "  ❤️  Health check: http://localhost:$FLASK_PORT/health"
  echo ""

  # Use venv if available, otherwise system python
  if [ -f ".venv/bin/python" ]; then
    .venv/bin/python run.py
  else
    python3 run.py
  fi
else
  echo ""
  echo "[2/2] 跳过启动 (--build-only)"
  echo "  手动启动: cd backend && PLANETX_DIST_DIR=$PLANETX_DIST_DIR python run.py"
  echo ""
  echo "  ✅ 构建完成"
fi
