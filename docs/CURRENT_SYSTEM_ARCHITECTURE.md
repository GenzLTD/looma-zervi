# 当前系统架构与部署状态

> **版本：** 1.0 · **更新日期：** 2026-07-09  
> **状态：** ✅ 生产环境运行中  
> **负责人：** Jason

---

## 📊 架构概览

### 系统拓扑图
```
用户访问
    ↓
前端页面 (http://47.115.168.107)
    ↓
前端 Nginx (反向代理)
    ↓ (转发 /v1/ 请求)
后端域名 (api.genz.ltd)
    ↓ (DNS解析)
后端服务器 (1.14.202.161:80)
    ↓ (Nginx反向代理)
后端应用 (1.14.202.161:5200)
```

### 组件状态总览
| 组件 | 地址/配置 | 状态 | 说明 |
|------|-----------|------|------|
| **前端页面** | http://47.115.168.107 | ✅ 运行中 | 备案后将切换为 szbolent.cn |
| **前端 Nginx** | `/v1/` → http://api.genz.ltd/v1/ | ✅ 已配置 | 已切换至新域名 |
| **后端 DNS** | api.genz.ltd → 1.14.202.161 | ✅ 生效 | 域名解析正常 |
| **后端 Nginx** | 1.14.202.161:80 → :5200 | ✅ 运行中 | 反向代理配置正常 |
| **Looma API** | 1.14.202.161:5200 | ✅ 运行中 | 包含 58,059 首诗词 |

---

## 🔧 详细配置

### 1. 前端部署配置

**当前访问地址**：
- 主站：http://47.115.168.107
- PlanetX（求职者/人格测试）：http://47.115.202.161/
- T空间（HR/企业工作台）：http://47.115.202.161/tspace/
- Bolent 诗词门户：http://47.115.202.161/bolent/
- API 健康检查：http://47.115.202.161/health

**Nginx 配置要点**：
```nginx
# 前端 Nginx 配置（部分）
server {
    listen 80;
    server_name 47.115.168.107;
    
    location / {
        root /path/to/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
    
    # API 请求转发到后端
    location /v1/ {
        proxy_pass http://api.genz.ltd/v1/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. 后端部署配置

**服务器信息**：
- IP 地址：1.14.202.161
- 操作系统：Ubuntu/CentOS（需确认）
- Python 版本：3.12+（根据 `pyproject.toml` 要求）

**后端应用**：
- 端口：5200
- 框架：Python Flask + Gunicorn
- 进程管理：systemd 或 supervisor
- 数据库：SQLite（开发）/ PostgreSQL（生产）

**Nginx 反向代理配置**：
```nginx
# 后端 Nginx 配置
server {
    listen 80;
    server_name api.genz.ltd;
    
    location / {
        proxy_pass http://127.0.0.1:5200;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # 健康检查端点
    location /health {
        proxy_pass http://127.0.0.1:5200/health;
        access_log off;
    }
}
```

**DNS 配置**：
```
api.genz.ltd.    IN    A    1.14.202.161
```

### 3. 数据统计

**诗词数据库**：
- 诗词总数：58,059 首
- 数据来源：本地 RAG 向量库
- 存储位置：`backend/src/rag/` 目录下

**用户数据**：
- 内测账号：4 个种子账号
- 密码：统一为 `looma123`
- 存储：SQLite 数据库（`looma.db`）

**API 端点**：
- 认证：`/v1/auth/*`（微信登录、JWT 验证）
- 人格测试：`/v1/game/*`
- 问答服务：`/v1/ask/*`
- 诗词搜索：`/v1/poetry/*`
- 企业功能：`/v1/enterprise/*`
- 报告生成：`/v1/reports/*`

---

## 🔍 健康检查

### 1. 服务状态检查

**API 健康检查**：
```bash
# 检查后端服务
curl -f http://api.genz.ltd/health
# 或直接检查后端
curl -f http://1.14.202.161:5200/health
```

**端口监听检查**：
```bash
# 检查后端应用端口
netstat -tlnp | grep :5200
# 或
ss -tlnp | grep :5200

# 检查 Nginx 端口
netstat -tlnp | grep :80
```

**进程状态检查**：
```bash
# 检查 Gunicorn 进程
ps aux | grep gunicorn

# 检查 Nginx 进程
ps aux | grep nginx
```

### 2. 域名解析检查

```bash
# 检查 DNS 解析
nslookup api.genz.ltd
# 或
dig api.genz.ltd

# 检查网络连通性
ping -c 4 1.14.202.161
curl -I http://api.genz.ltd/health
```

### 3. 日志检查

**Nginx 访问日志**：
```bash
tail -f /var/log/nginx/access.log
```

**Nginx 错误日志**：
```bash
tail -f /var/log/nginx/error.log
```

**应用日志**：
```bash
# Gunicorn 日志
tail -f /var/log/looma-backend.log

# 或 systemd 日志
journalctl -u looma-backend -f
```

---

## 🚨 故障排除指南

### 常见问题与解决方案

#### 问题1：API 请求返回 502 Bad Gateway
**可能原因**：
1. 后端应用未运行
2. Nginx 配置错误
3. 端口被占用

**解决步骤**：
1. 检查后端进程状态
   ```bash
   systemctl status looma-backend
   # 或
   ps aux | grep python
   ```
2. 重启后端服务
   ```bash
   systemctl restart looma-backend
   ```
3. 检查 Nginx 配置
   ```bash
   nginx -t
   systemctl restart nginx
   ```

#### 问题2：域名无法解析
**可能原因**：
1. DNS 配置错误
2. 网络问题
3. 防火墙阻止

**解决步骤**：
1. 检查 DNS 解析
   ```bash
   dig api.genz.ltd
   ```
2. 检查防火墙规则
   ```bash
   iptables -L -n
   # 或
   ufw status
   ```
3. 临时使用 IP 访问测试

#### 问题3：前端页面无法加载
**可能原因**：
1. Nginx 配置错误
2. 静态文件缺失
3. 权限问题

**解决步骤**：
1. 检查 Nginx 配置
   ```bash
   nginx -t
   ```
2. 检查静态文件目录
   ```bash
   ls -la /path/to/frontend/dist/
   ```
3. 检查文件权限
   ```bash
   chmod -R 755 /path/to/frontend/dist/
   ```

---

## 🔄 部署与更新流程

### 1. 后端更新流程

```bash
# 1. 登录服务器
ssh root@1.14.202.161

# 2. 进入项目目录
cd /root/looma-zervi/backend

# 3. 拉取最新代码
git pull origin main

# 4. 更新依赖（如果需要）
source venv/bin/activate
pip install -r requirements.txt

# 5. 重启服务
systemctl restart looma-backend

# 6. 检查服务状态
systemctl status looma-backend
curl http://localhost:5200/health
```

### 2. 前端更新流程

```bash
# 1. 本地构建前端
cd /Users/jason/Projects/looma-zervi/frontend
npm run build:prod

# 2. 上传到服务器
scp -r dist/* root@1.14.202.161:/var/www/looma-frontend/

# 3. 重启 Nginx
ssh root@1.14.202.161 "systemctl reload nginx"

# 4. 验证更新
curl -I http://47.115.168.107
```

### 3. 数据库更新流程

```bash
# 1. 备份当前数据库
cp /root/looma-zervi/data/looma.db /root/looma-zervi/data/looma.db.backup.$(date +%Y%m%d)

# 2. 应用迁移（如果有）
cd /root/looma-zervi/backend
source venv/bin/activate
python -m alembic upgrade head

# 3. 验证数据完整性
python -c "from src.db.manager import DatabaseManager; db = DatabaseManager('/root/looma-zervi/data/looma.db'); print('Tables:', db.list_tables())"
```

---

## 📈 监控与告警

### 1. 基础监控指标

**服务器监控**：
- CPU 使用率：`< 80%`
- 内存使用率：`< 85%`
- 磁盘使用率：`< 90%`
- 网络流量：监控异常峰值

**应用监控**：
- API 响应时间：P95 `< 2s`
- 错误率：`< 1%`
- 活跃连接数：监控并发量
- 诗词查询性能：平均 `< 500ms`

### 2. 告警配置

**关键告警项**：
1. **服务不可用**：HTTP 状态码非 200 持续 5 分钟
2. **高错误率**：API 错误率 > 5%
3. **性能下降**：平均响应时间 > 3s
4. **资源耗尽**：内存使用率 > 90%
5. **磁盘空间**：剩余空间 < 10%

**告警通知**：
- 邮件通知：运维团队
- 即时消息：飞书/钉钉群
- 电话通知：紧急情况

### 3. 监控工具建议

**基础监控**：
- `top` / `htop`：实时系统监控
- `netstat` / `ss`：网络连接监控
- `df` / `du`：磁盘空间监控

**应用监控**：
- Flask 日志分析
- Nginx 访问日志分析
- 自定义健康检查端点

**可选专业工具**：
- Prometheus + Grafana
- ELK Stack（日志分析）
- New Relic / Datadog（APM）

---

## 🔐 安全配置

### 1. 防火墙配置

```bash
# 只开放必要端口
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS（未来）
ufw enable
```

### 2. SSL/TLS 配置（未来）

```nginx
# HTTPS 配置示例（备案后启用）
server {
    listen 443 ssl;
    server_name szbolent.cn www.szbolent.cn;
    
    ssl_certificate /etc/letsencrypt/live/szbolent.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/szbolent.cn/privkey.pem;
    
    # 其他配置...
}
```

### 3. API 安全

**JWT 配置**：
- 密钥强度：至少 32 位随机字符串
- 过期时间：access token 1 小时，refresh token 7 天
- 刷新机制：支持 token 刷新

**速率限制**：
```python
# Flask-Limiter 配置示例
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["100 per minute", "10 per second"]
)
```

**输入验证**：
- 所有 API 参数验证
- SQL 注入防护
- XSS 防护

---

## 📋 维护检查清单

### 每日检查
- [ ] API 健康检查：`curl -f http://api.genz.ltd/health`
- [ ] 服务器资源监控：CPU、内存、磁盘
- [ ] 错误日志检查：`tail -100 /var/log/nginx/error.log`
- [ ] 备份状态检查：数据库备份是否成功

### 每周检查
- [ ] 安全更新：`apt update && apt upgrade`
- [ ] 日志轮转：检查日志文件大小
- [ ] 数据库优化：清理临时数据
- [ ] 性能分析：慢查询分析

### 每月检查
- [ ] 证书更新（未来 HTTPS）
- [ ] 安全扫描：漏洞扫描
- [ ] 容量规划：预测资源需求
- [ ] 备份恢复测试：验证备份可用性

---

## 📞 紧急联系人

| 角色 | 负责人 | 联系方式 | 职责 |
|------|--------|----------|------|
| **系统运维** | Jason | 待定 | 服务器维护、部署、监控 |
| **后端开发** | Jason | 待定 | API 开发、Bug 修复 |
| **前端开发** | 待定 | 待定 | 前端页面、用户体验 |
| **产品经理** | 待定 | 待定 | 需求沟通、优先级 |

### 紧急响应流程
1. **发现问题**：监控告警或用户报告
2. **初步诊断**：检查日志，确定问题范围
3. **通知负责人**：根据问题类型联系相应人员
4. **应急处理**：根据预案采取措施
5. **根本原因分析**：问题解决后进行复盘
6. **预防措施**：更新文档和预案

---

## 📝 变更记录

| 日期 | 版本 | 变更内容 | 负责人 |
|------|------|----------|--------|
| 2026-07-09 | 1.0 | 初始文档，记录当前架构 | Jason |
| 2026-07-09 | - | 执行冒烟测试，8/8测试通过 | 自动化脚本 |
| 2026-07-06 | - | 切换前端 Nginx 代理到 api.genz.ltd | Jason |
| 2026-07-05 | - | 部署后端到 1.14.202.161:5200 | Jason |
| 2026-07-04 | - | 配置 DNS 解析 api.genz.ltd | Jason |
| 2026-07-03 | - | 前端部署到 47.115.168.107 | Jason |

---

**文档状态**：✅ 当前有效 · 🔄 持续更新 · 📋 运维参考 · ✅ 冒烟测试通过

**最后验证时间**：2026-07-09 11:56  
**验证结果**：✅ 冒烟测试8/8通过，所有组件正常运行，架构稳定  
**测试报告**：[SMOKE_TEST_REPORT_20260709.md](./SMOKE_TEST_REPORT_20260709.md)

---

## 相关：职业时间序列（2026-07-29）

产品主线从「快照测评」转向「行为时间序列」。契约与一期 backlog：

- [TIMELINE_EVENT_MODEL.md](./TIMELINE_EVENT_MODEL.md)
- [TIMELINE_PHASE1_BACKLOG.md](./TIMELINE_PHASE1_BACKLOG.md)
- `backend/contracts/timeline.v1.json`

与 `product_events`（漏斗）、`narrative_events`（叙事）、`trust_memories`（信任证据）边界见模型文档 §1。参赛材料不作为本层真源。

