#!/usr/bin/env bash
# ============================================================================
# 摘块预演门禁（macOS / Linux）
# ============================================================================
#
# 证明目标：
#   摘掉 nginx 里 genz.ltd / www.genz.ltd 的 server 块之后，
#   ① api.genz.ltd 的 /health 与 /v1/payment/webhook/* 仍然可达；
#   ② tspace.genz.ltd 不受影响；
#   ③ genz.ltd / www.genz.ltd 落 catch-all → 404 Unknown host。
#
# 形态：加载「摘块后」的 HTTP-only 配置（对应 Cloudflare Flexible 回源 :80），
#       用 stub 顶 :5200。不依赖真 Flask、不依赖 SaaS 构建、不依赖 443。
#
# 用法：
#   bash scripts/cutover-test/run-test.sh
#   NGINX_PORT=18080 STUB_PORT=15200 bash scripts/cutover-test/run-test.sh
#
# 退出码：0 = 全绿；1 = 有断言失败或前置检查不过。
# ============================================================================

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/../.." && pwd)"
WORK="${HERE}/.generated"

NGINX_PORT="${NGINX_PORT:-18080}"
STUB_PORT="${STUB_PORT:-15200}"
STUB_HOST="127.0.0.1"
BASE="http://127.0.0.1:${NGINX_PORT}"

# 被测配置（真源）
CONF_MAIN="${REPO_ROOT}/docker/nginx.conf"
CONF_VULTR="${REPO_ROOT}/nginx-vultr.conf"
CONF_TEMPLATE="${HERE}/nginx-cutover-http.conf"

NGINX_PID=""
STUB_PID=""
FAILED=0

# ---------------------------------------------------------------- 输出工具
c_red()   { printf '\033[31m%s\033[0m' "$1"; }
c_green() { printf '\033[32m%s\033[0m' "$1"; }
c_dim()   { printf '\033[2m%s\033[0m' "$1"; }

pass() { printf '  %s  %s\n' "$(c_green 'PASS')" "$1"; }
fail() { printf '  %s  %s\n' "$(c_red 'FAIL')" "$1"; FAILED=1; }
note() { while IFS= read -r l; do printf '%s\n' "$(c_dim "       $l")"; done <<< "$1"; }

cleanup() {
    if [[ -n "${NGINX_PID}" ]] && kill -0 "${NGINX_PID}" 2>/dev/null; then
        kill "${NGINX_PID}" 2>/dev/null || true
    fi
    if [[ -n "${STUB_PID}" ]] && kill -0 "${STUB_PID}" 2>/dev/null; then
        kill "${STUB_PID}" 2>/dev/null || true
    fi
    wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------- 前置检查
echo
echo "=== 摘块预演门禁 (cutover-test) ==="
echo

for f in "${CONF_MAIN}" "${CONF_VULTR}" "${CONF_TEMPLATE}"; do
    if [[ ! -f "${f}" ]]; then
        fail "缺少文件：${f}"
        exit 1
    fi
done

# 抽取所有 server_name 指令的 token（按整 token 比对，避免 api.genz.ltd 被误判）
# 用法：awk '...' file —— 输出每行一个 token
SERVER_NAME_TOKENS_AWK='
    /^[[:space:]]*server_name[[:space:]]/ {
        line = $0
        sub(/;.*/, "", line)
        sub(/^[[:space:]]*server_name[[:space:]]*/, "", line)
        n = split(line, arr, /[[:space:]]+/)
        for (i = 1; i <= n; i++) if (arr[i] != "") print arr[i]
    }
'

# A1 — 真配置里不得残留裸域 server_name（本 PR 的核心断言）
BARE_NAME_AWK='
    /^[[:space:]]*server_name[[:space:]]/ {
        line = $0
        sub(/;.*/, "", line)
        sub(/^[[:space:]]*server_name[[:space:]]*/, "", line)
        n = split(line, arr, /[[:space:]]+/)
        for (i = 1; i <= n; i++) {
            if (arr[i] == "genz.ltd" || arr[i] == "www.genz.ltd") {
                print FNR ": " $0
                break
            }
        }
    }
'
for f in "${CONF_MAIN}" "${CONF_VULTR}"; do
    hits="$(awk "${BARE_NAME_AWK}" "${f}")"
    if [[ -n "${hits}" ]]; then
        fail "$(basename "${f}") 仍残留裸域 server 块"
        note "${hits}"
    else
        pass "$(basename "${f}") 无 genz.ltd / www.genz.ltd server_name"
    fi
done

# A2 — 模板与真配置的 Host 集合必须一致（防装置漂移）
hosts_of() { awk "${SERVER_NAME_TOKENS_AWK}" "$1" | sort -u; }
H_MAIN="$(hosts_of "${CONF_MAIN}")"
H_TPL="$(hosts_of "${CONF_TEMPLATE}")"
if [[ "${H_MAIN}" == "${H_TPL}" ]]; then
    pass "预演配置 Host 集合与 docker/nginx.conf 一致"
    note "$(echo "${H_MAIN}" | tr '\n' ' ')"
else
    fail "预演配置与 docker/nginx.conf 的 Host 集合不一致（装置漂移）"
    diff <(echo "${H_MAIN}") <(echo "${H_TPL}") | sed 's/^/       /' || true
    note "改了 docker/nginx.conf 的 server_name 后，请同步 nginx-cutover-http.conf"
fi

if [[ "${FAILED}" -ne 0 ]]; then
    echo
    echo "$(c_red '前置检查未通过，未启动预演。')"
    exit 1
fi

# ---------------------------------------------------------------- 找 nginx
find_nginx() {
    if [[ -n "${NGINX_BIN:-}" && -x "${NGINX_BIN}" ]]; then echo "${NGINX_BIN}"; return; fi
    if command -v nginx >/dev/null 2>&1; then command -v nginx; return; fi
    for p in /Applications/ServBay/sbin/nginx /opt/homebrew/bin/nginx \
             /usr/local/bin/nginx /usr/sbin/nginx; do
        [[ -x "${p}" ]] && { echo "${p}"; return; }
    done
    echo ""
}
NGINX="$(find_nginx)"
if [[ -z "${NGINX}" ]]; then
    fail "找不到 nginx 可执行文件（设 NGINX_BIN=/path/to/nginx 覆盖）"
    exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
    if command -v python3 >/dev/null 2>&1; then PYTHON_BIN="$(command -v python3)"; else PYTHON_BIN=""; fi
fi
if [[ -z "${PYTHON_BIN}" ]]; then
    fail "找不到 python3（设 PYTHON_BIN=/path/to/python3 覆盖）"
    exit 1
fi

echo
note "nginx   : ${NGINX}"
note "python3 : ${PYTHON_BIN}"
note "nginx port=${NGINX_PORT}  stub port=${STUB_PORT}"

# ---------------------------------------------------------------- 工作目录
rm -rf "${WORK}"
mkdir -p "${WORK}/www/tspaces"

cat > "${WORK}/mime.types" <<'EOF'
types {
    text/html                             html htm;
    text/css                              css;
    application/javascript                js mjs;
    application/json                      json;
    image/png                             png;
    image/svg+xml                         svg;
    font/woff2                            woff2;
}
EOF

cat > "${WORK}/www/tspaces/index.html" <<'EOF'
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>tspace stub</title></head>
<body><h1>tspace stub</h1><p>cutover-test placeholder SPA</p></body></html>
EOF

# ---------------------------------------------------------------- A3 真配置语法校验
# 删 server 块最容易的事故是改坏大括号配对（留下孤立 } 或吞掉下一块的开头）。
# 这里对两份真配置本身跑 nginx -t：只把 include 指到本地 mime.types，
# 并注释掉指向不存在的证书文件的行（本机没有生产证书）。
echo
echo "--- A3 真配置语法校验 ---"
for f in "${CONF_MAIN}" "${CONF_VULTR}"; do
    base="$(basename "${f}")"
    rendered="${WORK}/syntax-${base}"
    sed -e "s|include[[:space:]]*/etc/nginx/mime.types;|include ${WORK}/mime.types;|" \
        -e 's|listen[[:space:]]\{1,\}443[[:space:]]\{1,\}ssl[[:space:]]\{1,\}http2;|listen 1443;|' \
        -e 's|^\([[:space:]]*\)ssl_certificate[[:space:]]|\1#ssl_certificate |' \
        -e 's|^\([[:space:]]*\)ssl_certificate_key[[:space:]]|\1#ssl_certificate_key |' \
        "${f}" > "${rendered}"

    open_n="$(tr -cd '{' < "${rendered}" | wc -c | tr -d ' ')"
    close_n="$(tr -cd '}' < "${rendered}" | wc -c | tr -d ' ')"
    if [[ "${open_n}" != "${close_n}" ]]; then
        fail "${base} 大括号不配对：{ ×${open_n} vs } ×${close_n}"
        continue
    fi

    if "${NGINX}" -t -p "${WORK}/" -c "${rendered}" \
            > "${WORK}/nginx-t-${base}.log" 2>&1; then
        pass "${base} nginx -t 通过（braces ${open_n}/${close_n}）"
    else
        fail "${base} nginx -t 失败"
        sed 's/^/       /' "${WORK}/nginx-t-${base}.log" || true
    fi
done

if [[ "${FAILED}" -ne 0 ]]; then
    echo
    echo "$(c_red '前置检查未通过，未启动预演。')"
    exit 1
fi

# ---------------------------------------------------------------- 渲染预演配置
sed -e "s|__WORK__|${WORK}|g" \
    -e "s|__LISTEN__|${NGINX_PORT}|g" \
    -e "s|__UPSTREAM__|${STUB_HOST}:${STUB_PORT}|g" \
    -e "s|__MIME_TYPES__|${WORK}/mime.types|g" \
    -e "s|__TSPACE_ROOT__|${WORK}/www/tspaces|g" \
    "${CONF_TEMPLATE}" > "${WORK}/nginx.conf"

# ---------------------------------------------------------------- 起 stub
echo
echo "--- 启动 stub (${STUB_HOST}:${STUB_PORT}) ---"
"${PYTHON_BIN}" "${HERE}/stub_api.py" --host "${STUB_HOST}" --port "${STUB_PORT}" \
    > "${WORK}/stub.log" 2>&1 &
STUB_PID=$!

stub_ready=0
for _ in $(seq 1 40); do
    if curl -sf -o /dev/null "http://${STUB_HOST}:${STUB_PORT}/health" 2>/dev/null; then
        stub_ready=1; break
    fi
    sleep 0.25
done
if [[ "${stub_ready}" -ne 1 ]]; then
    fail "stub 未在 10s 内就绪"
    note "日志：${WORK}/stub.log"
    exit 1
fi
pass "stub 就绪"

# ---------------------------------------------------------------- 起 nginx
echo
echo "--- 校验并启动 nginx (端口 ${NGINX_PORT}) ---"
if ! "${NGINX}" -t -p "${WORK}/" -c "${WORK}/nginx.conf" > "${WORK}/nginx-t.log" 2>&1; then
    fail "nginx -t 配置校验失败"
    sed 's/^/       /' "${WORK}/nginx-t.log" || true
    exit 1
fi
pass "nginx -t 通过"

"${NGINX}" -p "${WORK}/" -c "${WORK}/nginx.conf" > "${WORK}/nginx.log" 2>&1
nginx_ready=0
for _ in $(seq 1 40); do
    if curl -s -o /dev/null -H 'Host: api.genz.ltd' "${BASE}/health" 2>/dev/null; then
        nginx_ready=1; break
    fi
    sleep 0.25
done
if [[ "${nginx_ready}" -ne 1 ]]; then
    fail "nginx 未在 10s 内响应"
    note "日志：${WORK}/nginx.log / ${WORK}/error.log"
    exit 1
fi
NGINX_PID="$(cat "${WORK}/nginx.pid" 2>/dev/null || echo '')"
pass "nginx 就绪 (pid ${NGINX_PID:-?})"

# ---------------------------------------------------------------- 断言
echo
echo "--- Host 探测断言 ---"

# check <desc> <host> <method> <path> <expect_code> <expect_body_substr>
check() {
    local desc="$1" host="$2" method="$3" path="$4" code="$5" body="$6"
    local resp got_code got_body

    if [[ "${method}" == "POST" ]]; then
        resp="$(curl -s -w '\n%{http_code}' -X POST -H "Host: ${host}" \
                -H 'Content-Type: application/json' -d '{}' "${BASE}${path}" 2>/dev/null)"
    else
        resp="$(curl -s -w '\n%{http_code}' -H "Host: ${host}" "${BASE}${path}" 2>/dev/null)"
    fi
    got_code="$(echo "${resp}" | tail -n 1)"
    got_body="$(echo "${resp}" | sed '$d')"

    if [[ "${got_code}" != "${code}" ]]; then
        fail "${desc}"
        note "期望 HTTP ${code}，实际 HTTP ${got_code}"
        note "body: $(echo "${got_body}" | head -c 200)"
        return
    fi
    if [[ -n "${body}" ]] && ! echo "${got_body}" | grep -qF "${body}"; then
        fail "${desc}"
        note "HTTP ${got_code} 正确，但 body 未含 '${body}'"
        note "body: $(echo "${got_body}" | head -c 200)"
        return
    fi
    pass "${desc}  ${got_code}"
}

check "api /health → 200 stub ok"                 api.genz.ltd   GET  /health                         200 '"status": "ok"'
check "api / → 404 Use /v1（无营销壳）"            api.genz.ltd   GET  /                               404 'Use /v1'
check "api POST /v1/payment/webhook/stripe → 200"  api.genz.ltd   POST /v1/payment/webhook/stripe     200 '"received": true'
check "tspace / → 200 tspace stub"                 tspace.genz.ltd GET /                               200 'tspace stub'
check "genz.ltd / → 404 Unknown host（块已摘）"    genz.ltd       GET  /                               404 'Unknown host'
check "www.genz.ltd / → 404 Unknown host（块已摘）" www.genz.ltd  GET  /                               404 'Unknown host'

# ---------------------------------------------------------------- 结论
echo
if [[ "${FAILED}" -eq 0 ]]; then
    echo "$(c_green '全绿：摘块不切 api webhook，不误伤 tspace，裸域落 catch-all。')"
    echo
    note "不能代替：真 Flask、真 SaaS 构建、HTTPS 443、DNS 真实切换。"
    echo
    exit 0
fi
echo "$(c_red '有断言失败，见上。')"
echo
note "stub 日志：${WORK}/stub.log"
note "nginx 日志：${WORK}/error.log"
echo
exit 1
