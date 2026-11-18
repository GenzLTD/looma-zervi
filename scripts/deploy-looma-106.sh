#!/usr/bin/env bash
# looma 宿主部署到新机。只写 ~/looma，不碰 ~/thomas，不碰 gfcc-kernel。
# 用法:
#   DRY_RUN=1 scripts/deploy-looma-106.sh          # 本机检查钉版和文件，不连服务器
#   scripts/deploy-looma-106.sh <sha>              # 在服务器上执行，代码已由 CI rsync 到 releases/<sha>
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

say() { echo "[looma-deploy] $*"; }

# 唯一真相源：backend/THOMAS_CORE_PIN 第一行（thomas-core 合入后的 squash SHA）。
# 不再在脚本里硬编码 PIN_EXPECTED —— 那是双点不同步的根源。
# check_tree 只接受合法 40 位 hex SHA；TODO/占位符/短 SHA 一律拒绝（fail-closed）。
read_pin() {
  head -n 1 "$1/backend/THOMAS_CORE_PIN" | tr -d '[:space:]'
}

valid_sha() {
  [[ "$1" =~ ^[0-9a-fA-F]{40}$ ]]
}

check_tree() {
  local root="$1"
  local pin
  pin="$(read_pin "$root")"
  if ! valid_sha "$pin"; then
    echo "FATAL: THOMAS_CORE_PIN=[$pin] 不是合法 40 位 SHA（占位符/未填/格式错）；" >&2
    echo "       须在 Mac squash 合入 thomas PR #2 后，填入 main 上的 merge SHA。" >&2
    exit 1
  fi
  [ -f "$root/backend/src/thomas_core/routes/invitation_routes.py" ] || {
    echo "FATAL: 钉版树里没有 invitation_routes.py" >&2
    exit 1
  }
  [ -f "$root/scripts/looma-backend.service" ] || {
    echo "FATAL: 缺 looma-backend.service" >&2
    exit 1
  }
  [ -f "$root/scripts/looma-nginx.conf" ] || {
    echo "FATAL: 缺 looma-nginx.conf" >&2
    exit 1
  }
}

if [ "${DRY_RUN:-0}" = "1" ]; then
  check_tree "$ROOT"
  say "dry-run OK"
  say "pin=$(read_pin "$ROOT") (from backend/THOMAS_CORE_PIN)"
  say "process=127.0.0.1:5200 via gunicorn"
  say "nginx=host :80 -> 127.0.0.1:5200"
  say "untouched=~/thomas and gfcc-kernel"
  say "secrets stay in ~/looma/.env on the server; this script does not write them"
  exit 0
fi

SHA="${1:?usage: deploy-looma-106.sh <commit-sha>}"
case "$SHA" in
  [0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]*) ;;
  *) echo "FATAL: bad sha" >&2; exit 1 ;;
esac
if [ "${#SHA}" -gt 40 ]; then
  echo "FATAL: bad sha" >&2
  exit 1
fi

APP="$HOME/looma"
REL="$APP/releases/$SHA"
CURRENT="$APP/current"
VENV="$APP/.venv"
KEEP=3

[ -d "$REL/backend" ] || { echo "FATAL: 发布目录不存在: $REL" >&2; exit 1; }
check_tree "$REL"
[ -f "$APP/.env" ] || { echo "FATAL: 先在服务器放好 $APP/.env（chmod 600），CI 不写凭据" >&2; exit 1; }

mkdir -p "$APP/data" "$APP/logs" "$APP/bin"
if [ ! -x "$VENV/bin/python" ]; then
  say "创建 venv"
  if command -v python3.12 >/dev/null 2>&1; then
    python3.12 -m venv "$VENV"
  else
    python3 -m venv "$VENV"
  fi
fi

say "安装依赖"
"$VENV/bin/pip" install -q --disable-pip-version-check -r "$REL/backend/requirements.txt"

say "切换 current → $SHA"
ln -sfn "$REL" "$CURRENT"
printf 'GIT_COMMIT=%s\n' "$SHA" > "$APP/deploy.env"
install -m 644 "$REL/scripts/looma-backend.service" /tmp/looma-backend.service
sudo cp /tmp/looma-backend.service /etc/systemd/system/looma-backend.service
sudo systemctl daemon-reload
sudo systemctl enable looma-backend
sudo systemctl restart looma-backend

ok=""
for _ in $(seq 1 40); do
  sleep 1
  if curl -sf -m 3 "http://127.0.0.1:5200/health" 2>/dev/null | grep -q 'looma-backend'; then
    ok=1
    break
  fi
done

if [ -z "$ok" ]; then
  PREV="$(ls -1t "$APP/releases" | grep -v "^${SHA}$" | head -1 || true)"
  if [ -n "$PREV" ]; then
    ln -sfn "$APP/releases/$PREV" "$CURRENT"
    printf 'GIT_COMMIT=%s\n' "$PREV" > "$APP/deploy.env"
    sudo systemctl restart looma-backend
    say "ROLLBACK → $PREV"
  else
    sudo systemctl stop looma-backend || true
  fi
  say "health FAIL"
  tail -50 "$APP/logs/looma-backend.log" 2>/dev/null || true
  exit 1
fi

if ! command -v nginx >/dev/null 2>&1; then
  say "安装 nginx"
  sudo apt-get update -y
  sudo apt-get install -y nginx
fi
sudo cp "$REL/scripts/looma-nginx.conf" /etc/nginx/sites-available/looma.conf
sudo ln -sfn /etc/nginx/sites-available/looma.conf /etc/nginx/sites-enabled/looma.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl reload nginx

ls -1t "$APP/releases" | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -rf "$APP/releases/$old"
done
install -m 755 "$REL/scripts/deploy-looma-106.sh" "$APP/bin/deploy-looma-106.sh"
say "deploy OK: $SHA"
