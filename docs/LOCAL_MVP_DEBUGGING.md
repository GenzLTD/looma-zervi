# Looma-Zervi 本地MVP联调内测指南

本文档介绍如何在本地启动完整的MVP联调内测环境，包括后端、前端Web服务和小程序开发环境。

> **没有 Docker / 没有 ServBay？** 请先看 [LOCAL_DEV_MINIMAL_SETUP.md](LOCAL_DEV_MINIMAL_SETUP.md) ——
> 最小依赖三步启动（后端 venv + vite 代理），本文的一键脚本与容器化组件均为可选增强。
> 注意：`start-full-mvp.sh` 会重复拉起前端并抢占 5173/5174 端口，与手动启动冲突，分步启动是推荐路径。

## 📋 系统要求

### 必需软件
- **Node.js 18+** (建议使用 LTS 版本)
- **pnpm 8+** (包管理器)
- **Python 3.10+** (markitdown 依赖要求)
- **Docker Desktop** (可选，用于 ChromaDB 容器)

### 推荐环境
- macOS / Linux / WSL2 (Windows)
- 内存: 8GB+ (推荐 16GB)
- 磁盘空间: 2GB+

## 🚀 快速启动

### 一键启动完整环境

```bash
# 在项目根目录执行
./scripts/start-full-mvp.sh
```

这个脚本会自动：
1. ✅ 检查环境依赖 (Node.js, Python, pnpm, Docker)
2. ✅ 设置后端Python虚拟环境
3. ✅ 启动Flask后端 (:5200)
4. ✅ 启动PlanetX前端 (:5173)
5. ✅ 启动T-space前端 (:5174) 
6. ✅ 配置小程序开发环境
7. ✅ 启动ChromaDB向量数据库 (:8000)

### 手动分步启动

如果遇到问题，可以手动分步启动：

```bash
# 1. 启动后端
cd backend
./dev.sh  # 或: python run.py

# 2. 启动前端Web服务 (新终端)
cd frontend
pnpm install
pnpm --filter @looma/planetx dev  # PlanetX (:5173)
pnpm --filter @looma/saas dev     # T-space (:5174)

# 3. 小程序配置
cd frontend/packages/miniprogram
# 确保 config.ts 指向本地后端: http://127.0.0.1:5200
# 微信开发者工具导入此目录，设置"不校验合法域名"
```

## 🌐 服务访问地址

| 服务 | 地址 | 用途 |
|------|------|------|
| **后端API** | `http://localhost:5200` | RESTful API 接口 |
| **PlanetX (C端)** | `http://localhost:5173` | 求职者端Web应用 |
| **T-space (B端)** | `http://localhost:5174` | HR企业端Web应用 |
| **ChromaDB** | `http://localhost:8000` | 向量数据库 (可选) |
| **健康检查** | `http://localhost:5200/health` | 后端服务状态 |

## 📱 小程序本地联调

### 准备工作
1. **安装微信开发者工具**
   - 下载地址: https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html

2. **配置小程序**
   ```bash
   cd frontend/packages/miniprogram
   
   # 检查配置
   cat utils/config.ts | grep API_BASE
   # 应该显示: export const API_BASE = 'http://127.0.0.1:5200'
   
   # 如果需要修改
   sed -i '' "s|export const API_BASE = .*|export const API_BASE = 'http://127.0.0.1:5200' // dev 环境|g" utils/config.ts
   ```

3. **构建npm包**
   ```bash
   # 构建共享包
   pnpm run build:npm
   ```

### 微信开发者工具设置
1. **导入项目**: 选择 `frontend/packages/miniprogram` 目录
2. **项目设置** → **本地设置**:
   - ✅ 不校验合法域名、web-view域名、TLS版本
   - ✅ 开启调试模式
3. **工具** → **构建npm**
4. **编译**: 点击编译按钮

### 核心测试链路
按照以下顺序测试MVP核心功能：

1. **登录流程** (`app.ts` / `pages/splash`)
   - 测试微信登录 (`wechatLogin`)
   - 验证JWT令牌获取

2. **主页面** (`pages/hub/index`)
   - 加载用户个人信息
   - 显示游戏进度和任务

3. **提问功能** (`pages/ask/index`)
   - 测试RAG问答
   - 验证 `ask_rag` consent 流程

4. **结果分享** (`pages/result/index`)
   - 测试分享功能
   - 验证 `profile_share` consent 流程

## 🔧 环境配置

### 后端环境变量
复制并修改 `backend/.env.example` 到 `backend/.env`:

```bash
# Flask
FLASK_ENV=development
FLASK_PORT=5200

# 数据库
DATABASE_PATH=./data/looma.db

# 诗词向量库
POETRY_CHROMA_PATH=data/poetry_full

# JWT密钥
JWT_SECRET=dev-secret-change-in-production

# 微信小程序 (开发模式跳过验证)
WECHAT_APPID=your_wechat_appid
WECHAT_SECRET=your_wechat_secret
WECHAT_DEV_MODE=true

# DeepSeek API (可选)
DEEPSEEK_API_KEY=your_deepseek_api_key

# CORS配置
CORS_ORIGINS=http://localhost:5173,http://localhost:5174
```

### 重要配置说明
1. **WECHAT_DEV_MODE=true**: 开发模式跳过微信登录验证
2. **POETRY_CHROMA_PATH**: 指向诗词向量库路径
3. **CORS_ORIGINS**: 允许的前端域名

## 🧪 测试验证

### API合规测试
```bash
# P0级别合规测试
bash scripts/verify-p0-local.sh

# 完整本地彩排
bash scripts/rehearsal-local.sh
```

### 小程序专用测试
```bash
# 小程序本地联调脚本
bash scripts/start-miniprogram-local.sh
```

### Web端E2E测试
```bash
cd frontend
pnpm e2e:live  # 实时环境测试
```

## 🔍 调试与监控

### 日志文件
- **后端日志**: `/tmp/looma-backend.log`
- **PlanetX日志**: `/tmp/planetx.log`
- **T-space日志**: `/tmp/saas.log`
- **ChromaDB日志**: `/tmp/chromadb.log`

### 实时查看日志
```bash
# 后端日志
tail -f /tmp/looma-backend.log

# PlanetX日志
tail -f /tmp/planetx.log

# 所有日志
tail -f /tmp/looma-backend.log /tmp/planetx.log /tmp/saas.log
```

### 服务状态检查
```bash
# 检查所有服务状态
## 🚀 内测部署配置（gunicorn）

对于内测环境，建议使用gunicorn多worker部署以提高并发能力：

### 1. gunicorn配置
创建 `backend/gunicorn_config.py`：
```python
# backend/gunicorn_config.py
import multiprocessing

# 工作进程数 = CPU核心数 × 2 + 1
workers = multiprocessing.cpu_count() * 2 + 1

# 工作进程类型
worker_class = "sync"

# 绑定地址和端口
bind = "0.0.0.0:5200"

# 超时设置（LLM请求可能较长）
timeout = 120

# 日志配置
accesslog = "-"
errorlog = "-"
loglevel = "info"

# 进程名
proc_name = "looma-backend"

# 优雅重启
graceful_timeout = 30
```

### 2. 启动脚本
创建 `backend/start_gunicorn.sh`：
```bash
#!/bin/bash
# backend/start_gunicorn.sh

cd "$(dirname "$0")"

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 设置环境变量
export FLASK_ENV=production
export PYTHONPATH="$PWD:$PYTHONPATH"

# 启动gunicorn
exec gunicorn \
    --config gunicorn_config.py \
    "src.app:create_app()"
```

### 3. 系统服务配置（可选）
对于Linux系统，可以配置systemd服务：

```ini
# /etc/systemd/system/looma-backend.service
[Unit]
Description=Looma Backend Service
After=network.target

[Service]
Type=simple
User=looma
WorkingDirectory=/opt/looma-zervi/backend
Environment=FLASK_ENV=production
Environment=PYTHONPATH=/opt/looma-zervi/backend
ExecStart=/opt/looma-zervi/backend/venv/bin/gunicorn \
    --config gunicorn_config.py \
    "src.app:create_app()"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 4. 性能调优建议
根据压力测试结果调整：

| 并发级别 | workers | 建议配置 |
|----------|---------|----------|
| 低 (< 10并发) | 2-3 | `workers = 3` |
| 中 (10-50并发) | CPU核心数 × 1.5 | `workers = cpu_count() * 1.5` |
| 高 (> 50并发) | CPU核心数 × 2 + 1 | `workers = cpu_count() * 2 + 1` |

### 5. 监控指标
```bash
# 查看gunicorn状态
ps aux | grep gunicorn

# 查看进程数
pstree -p $(pgrep gunicorn)

# 监控内存
top -p $(pgrep -d',' gunicorn)

# 查看日志
tail -f /var/log/looma/backend.log
```

### 6. 与开发模式的对比

| 配置项 | 开发模式 (dev.sh) | 生产模式 (gunicorn) |
|--------|------------------|---------------------|
| 服务器 | Flask开发服务器 | gunicorn |
| 进程数 | 1 | 多进程 (根据CPU) |
| 并发处理 | 单请求 | 多请求并行 |
| 重启方式 | 手动 | 优雅重启 |
| 日志 | 控制台输出 | 文件/系统日志 |
| 适合场景 | 本地开发 | 内测/生产 |

### 7. 验证部署
```bash
# 验证gunicorn是否运行
curl http://localhost:5200/health

# 压力测试（使用移植的脚本）
cd /Users/jason/Projects/looma-zervi
python3 scripts/concurrency_test.py --concurrency 10 --requests 50

# 查看worker状态
gunicorn_pid=$(pgrep gunicorn)
if [ -n "$gunicorn_pid" ]; then
    echo "Gunicorn PID: $gunicorn_pid"
    ps -o pid,ppid,cmd --forest -p $gunicorn_pid
fi
```

## 🐛 常见问题

### 1. PlanetX连接到远程服务器而非本地后端
**现象**: PlanetX发送API请求到 `http://1.14.202.161` 而不是 `http://127.0.0.1:5200`

**原因**: 环境变量 `VITE_API_BASE` 未设置

**解决方案**:
```bash
# 方法1: 使用启动脚本（推荐）
./scripts/start-full-mvp.sh
# 或
./scripts/start-demo.sh

# 方法2: 手动设置环境变量
cd frontend
export VITE_API_BASE=http://127.0.0.1:5200
export VITE_API_BASE_URL=http://127.0.0.1:5200
pnpm --filter @looma/planetx dev

# 方法3: 验证环境变量
./scripts/test-planetx-api.sh
```

**验证**: 在浏览器控制台运行：
```javascript
console.log('API Base:', import.meta.env.VITE_API_BASE)
// 应该显示: http://127.0.0.1:5200
```

### 2. 端口冲突
如果端口被占用，可以修改配置：

```bash
# 修改后端端口 (backend/.env)
FLASK_PORT=5201

# 修改前端端口 (frontend/package.json scripts)
# PlanetX: "dev": "vite --port 5175"
# T-space: "dev": "vite --port 5176"
```

### 3. 依赖安装失败
```bash
# 清理并重新安装
cd backend
rm -rf venv
./dev.sh

cd frontend
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

### 4. 小程序构建问题
```bash
# 清理构建缓存
cd frontend/packages/miniprogram
rm -rf miniprogram_npm node_modules
pnpm install
pnpm run build:npm

# 微信开发者工具: 工具 → 清除缓存 → 重新构建npm
```

### 5. ChromaDB启动失败
如果Docker不可用，后端会自动降级到本地文件模式：
- 向量搜索功能受限
- 诗词RAG可能不可用
- 其他功能正常

## 📊 MVP内测清单

### 必须验证的功能
- [ ] 用户注册/登录 (Web + 小程序)
- [ ] 人格类型测试流程
- [ ] 诗词RAG问答 (`/v1/ask`)
- [ ] 企业信用查询 (`/v1/credit/check-company`)
- [ ] Consent授权流程
- [ ] 简历解析 (`/v1/resume/parse`)
- [ ] 岗位匹配 (`/v1/jobs/match`)
- [ ] 分享功能

### 平台兼容性
- [ ] Chrome/Safari/Firefox
- [ ] 微信开发者工具
- [ ] 移动端浏览器

### 性能要求
- [ ] 页面加载 < 3秒
- [ ] API响应 < 1秒
- [ ] 内存使用 < 500MB
- [ ] 并发用户数 ≥ 10

## 🚨 紧急问题处理

### 后端崩溃
```bash
# 查看崩溃原因
cat /tmp/looma-backend.log

# 重新启动
pkill -f "python run.py"
cd backend && ./dev.sh
```

### 前端无法访问
```bash
# 检查端口占用
lsof -i :5173
lsof -i :5174

# 重启前端
pkill -f "vite"
cd frontend
pnpm --filter @looma/planetx dev &
pnpm --filter @looma/saas dev &
```

### 数据库问题
```bash
# 重置开发数据库
cd backend
rm -f data/looma.db
python run.py
```

## 📈 下一步优化

### 短期目标 (P0)
- [ ] 完善错误处理日志
- [ ] 添加API文档 (Swagger)
- [ ] 配置CI/CD流水线

### 中期目标 (P1)
- [ ] 集成真实微信登录
- [ ] 部署ChromaDB到云服务
- [ ] 添加监控和告警

### 长期目标 (P2)
- [ ] 性能优化和缓存
- [ ] 多语言支持
- [ ] 高级分析功能

## 📞 技术支持

### 项目负责人
- **Jason**: PlanetX前端 + 小程序 + 后端API
- **szbenyx**: T-space前端 + 企业端功能

### 问题反馈
1. 查看相关日志文件
2. 运行验证脚本
3. 提交GitHub Issue
4. 联系项目负责人

---

**最后更新**: $(date +%Y-%m-%d)
**版本**: MVP v1.0