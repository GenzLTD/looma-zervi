# QCC 网关本地承接（ServBay :8998）— 腾讯 8998 退役配套

> **地位**：执行记录 / 操作手册。配套《天翼云中央机入驻手册》第 12.4 步拍板（2026-08-27）。
> **结论**：腾讯 `1.14.202.161:8998` 退役（资产可再生）；本地开发用 ServBay 自定义端口 `:8998` 承接同款 QCC MCP 网关端点；生产天翼直连官方 `agent.qcc.com`，不需要网关。

## 1. 8998 是什么

- `1.14.202.161:8998` = 企查查（QCC）MCP **反代网关**（nginx），由 `scripts/deploy-qcc-gateway-cn.sh` 部署，配置源 `deploy/nginx/qcc-gateway.conf`。
- 历史用途：海外线（Vultr `139.180.184.25`）→ 腾讯 8998 → 官方 `agent.qcc.com/mcp`。
- 现状：官方 2026-07-28「Agent-Native」调整后海外直连不通，后海外线已弃用 qcc（`QCC_ENABLED=false`、token 清空、`QCC_MCP_BASE_URL` 删除）；8998 无消费者（活体但 403）。
- 因此 8998 是**可重建资产**，退役不损失能力。

## 2. 资产清单（全部在本仓，可再生）

| 文件 | 用途 |
|------|------|
| `deploy/nginx/qcc-gateway.conf` | 腾讯版（生产/公网白名单 geo） |
| `deploy/nginx/qcc-gateway-local.conf` | **本地 ServBay 版**（监听 `127.0.0.1:8998`，无 geo） |
| `scripts/deploy-qcc-gateway-cn.sh` | 腾讯部署脚本（重建/回滚用） |
| `docs/QCC_GATEWAY_LOCAL.md` | 本文档 |

## 3. 本地 ServBay 接入（:8998）

### 方式 A：ServBay 面板
1. ServBay → 新建站点 → 类型「自定义」（或选 NGINX 引擎）
2. 端口填 `8998`（ServBay 支持自定义 HTTP/HTTPS 端口，输入数字即生效）
3. 把 `deploy/nginx/qcc-gateway-local.conf` 内容粘贴进站点 nginx 配置（或按 ServBay 配置方式引入）
4. 保存生效，确认只监听 `127.0.0.1`（本地安全边界）

### 方式 B：本机 nginx 直接加载
```bash
# 把本地 conf 挂进本机 nginx（macOS Homebrew nginx 示例）
ln -sf "$(pwd)/deploy/nginx/qcc-gateway-local.conf" /usr/local/etc/nginx/servers/qcc-gateway-local.conf
nginx -t && nginx -s reload
```

## 4. 验证

```bash
curl -s http://127.0.0.1:8998/health          # 期望 {"status":"ok",...}
# 无 token 直连应 401/403（鉴权由官方代理头透传）：
curl -s -o /dev/null -w '%{http_code}\n' \
  -H 'Accept: text/event-stream' \
  http://127.0.0.1:8998/mcp/company/stream     # 期望非 5xx
```

本地 looma 开发环境设置：
```
QCC_ENABLED=true
QCC_AUTH_TOKEN=<官方 Key>
QCC_MCP_BASE_URL=http://127.0.0.1:8998/mcp
```

LLM 调用与 QCC 并存：LLM 走 ServBay AI 网关 `127.0.0.1:11580`（OpenAI/Anthropic/Gemini 兼容）；QCC MCP 走 `:8998`（Streamable HTTP，非 OpenAI 兼容，二者不互替）。

## 5. 腾讯 8998 退役（待执行）

```bash
# 腾讯机（1.14.202.161）
sudo rm /etc/nginx/sites-enabled/qcc-gateway        # 或注释后 reload
sudo nginx -t && sudo systemctl reload nginx
docker ps | grep -iE 'qcc|8998'                     # 若 8998 绑独立进程/容器，确认归属再停
# 可选：云安全组删除 TCP 8998 入站规则
```

> 与「腾讯原地不动 = 全量冷备」不冲突：拆除的是 nginx 站点文件，冷备容器（looma-backend / chromadb / redis / ollama / pgvector）不受影响。

## 6. 生产说明（天翼）

- 天翼直连官方 `agent.qcc.com`（streamable HTTP），**不设** `QCC_MCP_BASE_URL`（`config.py` 默认即官方地址；`QCC_MCP_BASE_URL` 仅用于海外反代场景）。
- 海外线 qcc 已弃用，不回切。

## 7. 回滚

- 本地：停 ServBay 8998 站点 / 移除 nginx server 块即可，无副作用。
- 腾讯（若需重建）：`SSH_KEY=~/.ssh/looma-key.pem ./scripts/deploy-qcc-gateway-cn.sh`（含 ufw 白名单 + `/health` 自检 + `/mcp/` 401 冒烟）。
