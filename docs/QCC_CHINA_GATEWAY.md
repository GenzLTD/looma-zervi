# QCC 中国网关（海外征信出口）

海外 Vultr 容器无法直连 `agent.qcc.com`。在国内云机（`1.14.202.161`）部署 nginx 反代：

| 项 | 值 |
|----|-----|
| 网关 | `http://1.14.202.161:8998` |
| 海外环境变量 | `QCC_MCP_BASE_URL=http://1.14.202.161:8998/mcp` |
| 配置文件 | `deploy/nginx/qcc-gateway.conf` |
| 部署脚本 | `scripts/deploy-qcc-gateway-cn.sh` |

协议：企查查 MCP 为 **Streamable HTTP**（`POST` JSON-RPC 到 `/mcp/*/stream`）。`GET` 会返回 405「请求方式异常」。

```bash
SSH_KEY=~/.ssh/looma-key.pem ./scripts/deploy-qcc-gateway-cn.sh
```

安全组需放行 **TCP 8998**（建议仅 Vultr `139.180.184.25`）。

nginx 配置已内置 IP allowlist（`139.180.184.25` + localhost）；云厂商安全组请同步限制源 IP。
