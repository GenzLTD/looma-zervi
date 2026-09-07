# QCC 中国网关（海外征信出口）

海外 Vultr 容器无法直连 `agent.qcc.com`。在国内云机（`1.14.202.161` 腾讯云）部署 nginx 反代：

| 项 | 值 |
|----|-----|
| 网关 | `http://1.14.202.161:8998` |
| 海外环境变量 | `QCC_MCP_BASE_URL=http://1.14.202.161:8998/mcp` |
| 配置文件 | `deploy/nginx/qcc-gateway.conf`（线上同步于 `/etc/nginx/sites-enabled/qcc-gateway`） |
| 部署脚本 | `scripts/deploy-qcc-gateway-cn.sh` |

协议：企查查 MCP 为 **Streamable HTTP**（`POST` JSON-RPC 到 `/mcp/*/stream`）。`GET` 会返回 405「请求方式异常」。

> **2026-09-02 实地核实（探测人：运维）**：网关为腾讯机宿主 nginx 直挂 `:8998`（非 docker），`geo $qcc_gw_allowed` 白名单 = `127.0.0.1 / ::1 / 139.180.184.25(Vultr SG)`，其余来源一律 `403`。**非白名单来源 curl 得 403 属预期行为，不是故障**。健康探活：`curl http://1.14.202.161:8998/health`（仅本地/localhost 可达）。

登录腾讯机（`1.14.202.161`，Ubuntu，**root 拒绝 pubkey**）：

```bash
SSH_KEY=~/Downloads/looma_key.pem  # 下划线命名，勿用 ~/.ssh/looma-key.pem（连字符版无法登录）
ssh -i "$SSH_KEY" ubuntu@1.14.202.161
sudo -n  # ubuntu 免密 sudo 可用
```

> 历史坑：`~/.ssh/looma-key.pem`（连字符）与 `~/Downloads/looma_key.pem`（下划线）是两份不同 key；腾讯机只认 **ubuntu + Downloads 下划线版**。部署脚本内若仍写 `~/.ssh/looma-key.pem` 需改。

腾讯机同台还跑大陆 Looma 全家桶（docker：looma-backend `:5200`、chromadb `:8000`、redis `:6379`、ollama `:11434`、pgvector `:5433`，compose 在 `/opt/looma-zervi/docker/`，2026-09-02 有 `/opt/looma-zervi.p0-archive-20260902/` 归档与新部署痕迹）。

安全组需放行 **TCP 8998**（建议仅 Vultr `139.180.184.25`）。

nginx 配置已内置 IP allowlist（`139.180.184.25` + localhost）；云厂商安全组请同步限制源 IP。
