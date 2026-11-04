#!/usr/bin/env bash
# ============================================================================
# station_smoke.sh — 三站壳冒烟（looma 三轨现网拓扑版）
#
# 背景：quick_smoke_test.sh / smoke_test.sh 打的是已下线的腾讯云主机
#       （1.14.202.161 / 47.115.168.107），整体过期；本脚本对齐 2026-11 拓扑：
#         - 天翼 14.29.216.219      大陆轨（looma main，deploy_track=looma）
#         - SG   api.genz.ltd       新加坡生产（vultr tag 轨，deploy_track=vultr）
#         - FRA  45.76.84.90        预演台（可选，经 SSH 访问本机端口）
#       身份联邦/密钥层面的六断言复验见 Vultr 仓 scripts/ethos-parity-onekey.sh，
#       本脚本只管「壳活着 + 轨道身份正确 + 公网面正常」。
#
# 用法：bash scripts/station_smoke.sh
#   可选环境变量：
#     FRA_SSH   如 "looma-staging-fra"（配了才跑 FRA 断言，否则标 SKIP）
#     TIMEOUT   单请求超时秒数（默认 12）
#
# 退出码：FAIL>0 → 1
# ============================================================================
set -u

TIMEOUT="${TIMEOUT:-12}"
FRA_SSH="${FRA_SSH:-}"
TY_URL="${TY_URL:-http://14.29.216.219}"
SG_URL="${SG_URL:-https://api.genz.ltd}"
CIRCLE_URL="${CIRCLE_URL:-https://circle.genz.ltd/circle/api/me}"

PY=$(command -v python3 || command -v python)
pass=0; fail=0; skip=0

row() { # row NAME RESULT DETAIL
  case "$2" in
    PASS) echo "  ✅ PASS  $1  ($3)"; pass=$((pass+1));;
    FAIL) echo "  ❌ FAIL  $1  ($3)"; fail=$((fail+1));;
    SKIP) echo "  ⏭️  SKIP  $1  ($3)"; skip=$((skip+1));;
  esac
}

# 裸值 JSON 取键：字符串去引号，缺失/空 → "null"
jget() { "$PY" -c '
import sys, json
try: d = json.load(sys.stdin)
except Exception: print("null"); sys.exit(0)
v = d
for k in sys.argv[1].split("."):
    if isinstance(v, dict): v = v.get(k)
    else: v = None; break
print("null" if v in (None, "") else v)
' "$1" 2>/dev/null
}

health() { curl -s --max-time "$TIMEOUT" "$1/health" 2>/dev/null; }

echo "==========================================================================="
echo "🚀 looma 三站壳冒烟  $(date '+%Y-%m-%d %H:%M:%S')"
echo "==========================================================================="

# ---- S1 天翼：looma 轨身份 + tip 语义 ----
echo "── S1 天翼（$TY_URL，大陆轨 looma tip）"
H=$(health "$TY_URL")
if [ -n "$H" ]; then
  TR=$(printf '%s' "$H" | jget deploy_track)
  GC=$(printf '%s' "$H" | jget git_commit)
  LS=$(printf '%s' "$H" | jget looma_sha)
  KD=$(printf '%s' "$H" | jget looma_sha_kind)
  if [ "$TR" = "looma" ] && [ -n "$GC" ] && [ "$GC" != "null" ] && [ "$GC" = "$LS" ] \
     && [ "$KD" = "deploy_tip" ]; then
    row "S1 天翼 track=looma 且 tip=git_commit" PASS "sha=${GC:0:8} kind=$KD"
  else
    row "S1 天翼 track=looma 且 tip=git_commit" FAIL "track=$TR gc=${GC:0:8} ls=${LS:0:8} kind=$KD"
  fi
else
  row "S1 天翼 /health 可达" FAIL "无响应"
fi

# ---- S2 SG：vultr 轨身份 + join_pin 语义 ----
echo "── S2 SG（$SG_URL，生产 stack 轨）"
H=$(health "$SG_URL")
if [ -n "$H" ]; then
  TR=$(printf '%s' "$H" | jget deploy_track)
  GC=$(printf '%s' "$H" | jget git_commit)
  SS=$(printf '%s' "$H" | jget stack_sha)
  VT=$(printf '%s' "$H" | jget vultr_tag)
  LS=$(printf '%s' "$H" | jget looma_sha)
  KD=$(printf '%s' "$H" | jget looma_sha_kind)
  VT_OK=0
  case "$VT" in stack-v*) VT_OK=1;; esac
  if [ "$TR" = "vultr" ] && [ "$SS" = "$GC" ] && [ -n "$VT" ] && [ "$VT" != "null" ] \
     && [ "$VT_OK" = 1 ]; then
    row "S2 SG track=vultr 且 tip=stack_sha" PASS "tag=$VT stack=${SS:0:8}"
  else
    row "S2 SG track=vultr 且 tip=stack_sha" FAIL "track=$TR gc=${GC:0:8} ss=${SS:0:8} tag=$VT"
  fi
  # SG 的 looma_sha 应是 join PIN（≠ git_commit），kind=join_pin（新字段）
  if [ "$KD" = "join_pin" ]; then
    row "S2b SG looma_sha_kind=join_pin" PASS "pin=${LS:0:8}"
  elif [ "$LS" != "null" ] && [ "$LS" != "$GC" ]; then
    row "S2b SG looma_sha_kind=join_pin" SKIP "旧镜像无 kind 字段，但 PIN≠tip 成立（pin=${LS:0:8}）"
  else
    row "S2b SG looma_sha_kind=join_pin" FAIL "kind=$KD pin=${LS:0:8} gc=${GC:0:8}"
  fi
else
  row "S2 SG /health 可达" FAIL "无响应"
fi

# ---- S3 FRA：预演台身份（可选，需 FRA_SSH）----
echo "── S3 FRA（预演台，经 SSH）"
if [ -n "$FRA_SSH" ]; then
  H=$(ssh -o ConnectTimeout=15 -o BatchMode=yes "$FRA_SSH" \
      "curl -s --max-time 8 http://127.0.0.1:5200/health" 2>/dev/null)
  if [ -n "$H" ]; then
    TR=$(printf '%s' "$H" | jget deploy_track)
    VT=$(printf '%s' "$H" | jget vultr_tag)
    LS=$(printf '%s' "$H" | jget looma_sha)
    FR_OK=0
    case "$VT" in fra-rehearsal-*) FR_OK=1;; esac
    if [ "$TR" = "vultr" ] && [ "$FR_OK" = 1 ] && [ "$LS" = "null" ]; then
      row "S3 FRA 预演台标记正确" PASS "tag=$VT"
    else
      row "S3 FRA 预演台标记正确" FAIL "track=$TR tag=$VT looma_sha=$LS"
    fi
  else
    row "S3 FRA /health（经 SSH）" FAIL "无响应"
  fi
else
  row "S3 FRA 预演台标记" SKIP "未配 FRA_SSH"
fi

# ---- S4 公网功能面 ----
echo "── S4 公网功能面"
for pair in "天翼:$TY_URL" "SG:$SG_URL"; do
  name="${pair%%:*}"; base="${pair#*:}"
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" "$base/v1/endpoints")
  if [ "$code" = "200" ]; then
    row "S4 $name /v1/endpoints" PASS "200"
  else
    row "S4 $name /v1/endpoints" FAIL "$code"
  fi
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" "$base/v1/poetry/random?count=1")
  if [ "$code" = "200" ]; then
    row "S4 $name poetry API" PASS "200"
  else
    row "S4 $name poetry API" FAIL "$code"
  fi
done

# ---- S5 circle 鉴权墙 ----
echo "── S5 circle 公网鉴权墙"
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" "$CIRCLE_URL")
if [ "$code" = "401" ]; then
  row "S5 circle 匿名被拒（401）" PASS "401"
else
  row "S5 circle 匿名被拒（401）" FAIL "$code（若策略已改为公开只读，请同步更新本断言）"
fi

# ---- 汇总 ----
echo "==========================================================================="
echo "📊 结果：PASS=$pass FAIL=$fail SKIP=$skip"
echo "==========================================================================="
if [ "$fail" -gt 0 ]; then
  echo "❌ 有 $fail 项失败。排查顺序：health 字段（轨道身份）→ 端点存活 → 鉴权墙。"
  echo "   身份联邦/密钥层复验另跑 Vultr 仓 scripts/ethos-parity-onekey.sh"
  exit 1
fi
echo "🎉 壳冒烟通过（SKIP 不计失败）。"
exit 0
