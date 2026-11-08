#!/usr/bin/env bash
# 从 GitHub 托管运行器登录新机，把 looma 宿主同步过去再执行服务器侧脚本。
# 主机指纹只接受已经存好的 ECDSA P-256。对不上就退出，不放宽检查。
# 不把凭据写进 ~/looma/.env，也不要在日志里打出主机、密钥或指纹。
set -euo pipefail

host="${DEPLOY106_HOST:-}"
user="${DEPLOY106_USER:-ubuntu}"
key_text="${DEPLOY106_SSH_KEY:-}"
expected="${DEPLOY106_HOST_FINGERPRINT:-}"
action="${1:-}"
sha="${2:-}"

# 缺哪项就点名哪项。原先是三合一提示，看不出是配置没建还是建错了位置。
missing=()
[ -n "$host" ]     || missing+=("DEPLOY106_HOST")
[ -n "$key_text" ] || missing+=("DEPLOY106_SSH_KEY")
[ -n "$expected" ] || missing+=("DEPLOY106_HOST_FINGERPRINT")
if [ "${#missing[@]}" -gt 0 ]; then
  echo "missing env: ${missing[*]}" >&2
  exit 1
fi

# host 只接受裸主机名/IP：挡掉 scheme、路径、以及以 - 开头被当成 ssh 选项的情况。
case "$host" in
  *[!A-Za-z0-9.:_-]*|-*)
    echo "invalid DEPLOY106_HOST format" >&2
    exit 1
    ;;
esac

# 用户名校验，挡掉 user@host 或带选项注入的写法。
case "$user" in
  *[!A-Za-z0-9._-]*|-*|"")
    echo "invalid DEPLOY106_USER format" >&2
    exit 1
    ;;
esac

case "$action" in
  deploy)
    case "$sha" in
      [0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]*) ;;
      *)
        echo "bad sha" >&2
        exit 1
        ;;
    esac
    if [ "${#sha}" -gt 40 ]; then
      echo "bad sha" >&2
      exit 1
    fi
    ;;
  *)
    echo "usage: ci-ssh.sh deploy <sha>" >&2
    exit 1
    ;;
esac

root="$(cd "$(dirname "$0")/.." && pwd)"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
printf '%s\n' "$key_text" > "$tmp/key"
chmod 600 "$tmp/key"

scanned=""
for _attempt in 1 2 3; do
  scanned=$(ssh-keyscan -t ecdsa -T 10 "$host" 2>/dev/null | grep -v '^#' || true)
  if [ -n "$scanned" ]; then
    break
  fi
  sleep 2
done
if [ -z "$scanned" ]; then
  echo "host key scan failed" >&2
  exit 1
fi

matched=""
while IFS= read -r line; do
  [ -n "$line" ] || continue
  fp=$(printf '%s\n' "$line" | ssh-keygen -lf - | awk 'NR==1 { print $2 }')
  if [ "$fp" = "$expected" ]; then
    matched="$line"
    break
  fi
done <<EOF
$scanned
EOF
if [ -z "$matched" ]; then
  echo "host key fingerprint mismatch" >&2
  exit 1
fi
printf '%s\n' "$matched" > "$tmp/known_hosts"

ssh_opts=(
  -i "$tmp/key"
  -o BatchMode=yes
  -o IdentitiesOnly=yes
  -o ConnectTimeout=30
  -o StrictHostKeyChecking=yes
  -o UserKnownHostsFile="$tmp/known_hosts"
  -o HostKeyAlgorithms=ecdsa-sha2-nistp256
  -o UpdateHostKeys=no
)

export RSYNC_RSH="ssh -i $tmp/key -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=30 -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$tmp/known_hosts -o HostKeyAlgorithms=ecdsa-sha2-nistp256 -o UpdateHostKeys=no"
ssh "${ssh_opts[@]}" "${user}@${host}" "mkdir -p ~/looma/releases/${sha}/scripts"
rsync -az --delete \
  --exclude '.venv' \
  --exclude 'data' \
  --exclude '.env' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  "$root/backend/" "${user}@${host}:~/looma/releases/${sha}/backend/"
rsync -az \
  "$root/scripts/deploy-looma-106.sh" \
  "$root/scripts/looma-backend.service" \
  "$root/scripts/looma-nginx.conf" \
  "$root/scripts/ci-ssh.sh" \
  "${user}@${host}:~/looma/releases/${sha}/scripts/"
ssh "${ssh_opts[@]}" "${user}@${host}" "chmod 755 ~/looma/releases/${sha}/scripts/deploy-looma-106.sh && ~/looma/releases/${sha}/scripts/deploy-looma-106.sh ${sha}"
