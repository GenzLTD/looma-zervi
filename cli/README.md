# 🛸 Looma CLI

**职业成长平台的运维大脑** — 一站式命令行工具，管理 Looma-Zervi 的部署、诊断、征信查询和定时监控。

## 安装

```bash
# 安装到 looma 后端 venv（推荐）
cd cli && ./install.sh

# 独立安装
./install.sh --standalone
```

安装后即可使用 `looma` 命令。

## 命令总览

| 命令 | 功能 | 适用场景 |
|------|------|----------|
| `looma doctor` | 全链路智能诊断 | 排查故障、上线前检查 |
| `looma status` | 系统运行状态 | 快速了解全局健康 |
| `looma health` | API 快速健康检查 | CI/CD、监控脚本 |
| `looma deploy` | 一键部署 | 发布上线 |
| `looma credit` | 企业征信查询 | 合伙人背调、尽调 |
| `looma cron` | 定时监控告警 | 7x24 自动化运维 |

## 快速开始

```bash
# 1. 全面诊断
looma doctor

# 2. 查看系统状态
looma status

# 3. 查询企业征信
looma credit 深圳市腾讯计算机系统有限公司

# 4. 部署后端
looma deploy backend

# 5. 设置定时健康检查（每5分钟）
looma cron add --name "health-check" --interval 300 --alert
looma cron start --daemon
```

## 命令详解

### `looma doctor` — 智能诊断

自动检测 8 大类共 11+ 项指标：

- 网络与 DNS 解析
- API 各模块端点可用性
- SQLite 数据库完整性
- ChromaDB 向量库状态
- MCP Sidecar 连通性
- 本地进程运行状态
- 磁盘 / 内存资源
- SSH 远程连接（`--full` 模式）

```bash
looma doctor              # 基础诊断
looma doctor --full       # 含远程 SSH 诊断
looma doctor --json       # JSON 输出（CI 友好）
```

### `looma status` — 系统状态

检查 4 项核心指标：

- DNS 解析 (api.genz.ltd)
- API 健康端点
- 后端端口可达性 (1.14.202.161:5200)
- 前端服务器可达性 (47.115.168.107:80)

### `looma deploy` — 一键部署

```bash
looma deploy check                # 部署前检查
looma deploy backend              # 部署后端
looma deploy frontend             # 部署前端
looma deploy all                  # 全量部署
looma deploy backend --dry-run    # 预览模式
```

### `looma credit` — 企业征信

数据来源：企查查 (QCC) 官方 MCP 接口

```bash
looma credit 腾讯                 # 基础征信查询
looma credit 阿里巴巴 --detail    # 完整报告（含知识产权、司法案件）
looma credit 字节跳动 --json      # JSON 输出
```

### `looma cron` — 定时监控

```bash
looma cron add --name "api-monitor" --interval 600 --alert
looma cron list
looma cron run --name "api-monitor"
looma cron start --daemon
```

## 技术架构

```
looma CLI (Python + Click)
    │
    ├── HTTP → api.genz.ltd/v1/*        (REST API)
    ├── SSH  → 1.14.202.161 / 47.115.168.107  (运维)
    ├── MCP  → 127.0.0.1:8999           (MCP Sidecar)
    └── Local → SQLite / ChromaDB / ps  (本地诊断)
```

## 许可证

MIT License — 100% 自有知识产权
