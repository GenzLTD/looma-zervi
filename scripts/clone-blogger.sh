#!/usr/bin/env bash
# ============================================================
# clone-blogger.sh — 从陆游母版实例克隆出一个新博主实例
# ------------------------------------------------------------
# 输入：博主参数文件（bash KEY="value" 语法，见 bloggers/blogger.template.env）
# 输出：clones/<slug>/ 目录，内含可直接部署的：
#        - nginx.conf       (域名已替换)
#        - deploy.sh        (域名/仓库/分支已替换)
#        - backend.env      (CORS/JWT/域名已替换)
#        - README.md        (该博主专属部署说明)
#
# 用法：
#   bash scripts/clone-blogger.sh bloggers/libai.env
#
# 原理：不做模板副本（避免与母版漂移），直接从母版现有文件
#       docker/nginx.conf、scripts/deploy-overseas.sh、backend/.env.example
#       用 sed 做「母版域名 → 目标域名」的最长优先替换。
#       母版改了，克隆产物自动跟随。
# ============================================================

set -euo pipefail

# ── 母版实例的域名（基准）──
MOTHER_DOMAIN="genz.ltd"

# ── 项目根（脚本在 <root>/scripts 下）──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

log()  { echo "[clone-blogger] $*"; }
die()  { echo "[clone-blogger] 错误: $*" >&2; exit 1; }

# ── 读取参数文件 ──
if [ "$#" -ne 1 ]; then
    die "用法: bash scripts/clone-blogger.sh bloggers/<slug>.env"
fi
PARAM_FILE="$1"
[ -f "${PARAM_FILE}" ] || die "参数文件不存在: ${PARAM_FILE}"

# shellcheck source=/dev/null
source "${PARAM_FILE}"

# ── 校验必填 ──
[ -n "${BLOGGER_NAME:-}" ] || die "BLOGGER_NAME 必填"
[ -n "${BLOGGER_SLUG:-}" ] || die "BLOGGER_SLUG 必填"
[ -n "${MAIN_DOMAIN:-}" ] || die "MAIN_DOMAIN 必填"

# ── 推导默认域名 ──
WWW_DOMAIN="${WWW_DOMAIN:-www.${MAIN_DOMAIN}}"
API_DOMAIN="${API_DOMAIN:-api.${MAIN_DOMAIN}}"
APP_DOMAIN="${APP_DOMAIN:-app.${MAIN_DOMAIN}}"
TSPACE_DOMAIN="${TSPACE_DOMAIN:-tspace.${MAIN_DOMAIN}}"

# ── JWT_SECRET 处理 ──
if [ -z "${JWT_SECRET:-}" ] || [[ "${JWT_SECRET}" == REPLACE_* ]]; then
    JWT_SECRET="$(openssl rand -hex 32 2>/dev/null || echo "auto-generated-$(date +%s)")"
    log "JWT_SECRET 未填，已自动生成随机值"
fi
SECRET_KEY="$(openssl rand -hex 24 2>/dev/null || echo "flask-secret-$(date +%s)")"

# ── 输出目录 ──
OUT_DIR="${ROOT_DIR}/clones/${BLOGGER_SLUG}"
mkdir -p "${OUT_DIR}"
log "目标: ${OUT_DIR}"

# ── sed 工具：最长优先替换域名（顺序关键，api/tspace/www 先于裸域）──
#    母版域名可能含点，替换串用 | 做分隔符；值不含 & \ 时安全。
apply_domain_subst() {
    sed -e "s|api\.${MOTHER_DOMAIN}|${API_DOMAIN}|g" \
        -e "s|tspace\.${MOTHER_DOMAIN}|${TSPACE_DOMAIN}|g" \
        -e "s|www\.${MOTHER_DOMAIN}|${WWW_DOMAIN}|g" \
        -e "s|${MOTHER_DOMAIN}|${MAIN_DOMAIN}|g"
}

# ── 1. nginx.conf ──
if [ -f "${ROOT_DIR}/docker/nginx.conf" ]; then
    apply_domain_subst < "${ROOT_DIR}/docker/nginx.conf" > "${OUT_DIR}/nginx.conf"
    log "已生成 nginx.conf"
else
    die "缺母版 docker/nginx.conf"
fi

# ── 2. deploy.sh ──
if [ -f "${ROOT_DIR}/scripts/deploy-overseas.sh" ]; then
    apply_domain_subst < "${ROOT_DIR}/scripts/deploy-overseas.sh" \
        | sed -e "s|^REPO_URL=.*|REPO_URL=\"${REPO_URL:-https://gitee.com/szbenyx/looma-zervi.git}\"|" \
              -e "s|^BRANCH=.*|BRANCH=\"${BRANCH:-release/overseas}\"|" \
        > "${OUT_DIR}/deploy.sh"
    chmod +x "${OUT_DIR}/deploy.sh"
    log "已生成 deploy.sh"
else
    die "缺母版 scripts/deploy-overseas.sh"
fi

# ── 3. backend.env ──
if [ -f "${ROOT_DIR}/backend/.env.example" ]; then
    CORS="https://${MAIN_DOMAIN},https://${WWW_DOMAIN},https://${TSPACE_DOMAIN},https://${API_DOMAIN},https://${APP_DOMAIN}"
    apply_domain_subst < "${ROOT_DIR}/backend/.env.example" \
        | sed -e "s|^JWT_SECRET=.*|JWT_SECRET=${JWT_SECRET}|" \
              -e "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" \
              -e "s|^CORS_ORIGINS=.*|CORS_ORIGINS=${CORS}|" \
              -e "s|^GOOGLE_REDIRECT_URI=.*|GOOGLE_REDIRECT_URI=https://${API_DOMAIN}/v1/auth/google/callback|" \
              -e "s|^DEPLOY_REGION=.*|DEPLOY_REGION=${DEPLOY_REGION:-SG}|" \
        > "${OUT_DIR}/backend.env"
    log "已生成 backend.env"
else
    die "缺母版 backend/.env.example"
fi

# ── 4. README.md ──
cat > "${OUT_DIR}/README.md" <<EOF
# ${BLOGGER_TITLE:-${BLOGGER_NAME}} 实例

本目录由 \`scripts/clone-blogger.sh\` 从母版实例克隆生成，是一套**独立博主实例**的完整部署产物。

## 参数

| 项 | 值 |
|----|----|
| 博主名 | ${BLOGGER_NAME} |
| slug | ${BLOGGER_SLUG} |
| 主域 | ${MAIN_DOMAIN} |
| API 域 | ${API_DOMAIN} |
| App 域 | ${APP_DOMAIN} |
| T空间域 | ${TSPACE_DOMAIN} |
| 部署区域 | ${DEPLOY_REGION:-SG} |

## 部署步骤（在目标云主机上，root）

\`\`\`bash
# 1. 把本目录上传到目标机（或用 git 拉取后取 clones/${BLOGGER_SLUG}/）
scp -r clones/${BLOGGER_SLUG} root@<目标IP>:/opt/blogger-clone

# 2. 首次部署（装 Docker/nginx/证书 + 拉代码 + 起服务）
cd /opt/blogger-clone
bash deploy.sh

# 3. 把 backend.env 合并进 ${BLOGGER_SLUG} 的 backend/.env 真实密钥
#    （deploy.sh 会 clone 仓库到 /opt/looma-zervi，nginx 已用本目录 nginx.conf）
\`\`\`

> 完整「各配各的货」流程见 \`docs/BLOGGER_CLONE_GUIDE.md\`。
> 诗词库切分、人格题替换、品牌皮替换不在本脚本自动范围，按手册手工完成。

## 生成文件说明

- \`nginx.conf\`：域名已替换为 ${BLOGGER_SLUG} 的域名，其余与母版一致
- \`deploy.sh\`：域名/仓库/分支已替换
- \`backend.env\`：CORS/JWT/SECRET_KEY/域名已替换（还需手工补真实第三方密钥）
EOF
log "已生成 README.md"

# ── 5. 验证：产物目录内不应残留母版域名 ──
log "验证残留..."
LEAK="$(grep -rIn "genz\.ltd" "${OUT_DIR}" 2>/dev/null || true)"
if [ -n "${LEAK}" ]; then
    echo "!! 发现母版域名残留（需人工核对）:" >&2
    echo "${LEAK}" >&2
    exit 1
fi
log "无母版域名残留 ✓"

echo ""
log "========================================"
log "克隆完成。产物目录: ${OUT_DIR}"
log "  nginx.conf  / deploy.sh  / backend.env  / README.md"
log "下一步（「各配各的货」）:"
log "  1) 诗词库:   bash scripts/poetry-split-by-author.py --author ${BLOGGER_NAME}"
log "  2) 人格题:   改 backend/src/api/routes/game_routes.py 的 PERSONALITY_* 常量"
log "  3) 品牌皮:   改 frontend/packages/planetx/src/brand/tokens.css + 文案"
log "详见 docs/BLOGGER_CLONE_GUIDE.md"
log "========================================"
