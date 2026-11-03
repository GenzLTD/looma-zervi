# 冒烟测试指南

> **版本：** 1.0 · **更新日期：** 2026-07-09  
> **状态：** ✅ 生产环境就绪  
> **负责人：** 运维团队

---

## 📋 概述

冒烟测试是部署后对生产环境进行的快速功能验证，确保核心功能正常运行。本指南包含完整的测试流程、脚本使用方法和故障排查步骤。

## 🎯 测试目标

### 核心验证点
1. ✅ **网络连通性**：所有服务器和端口可达
2. ✅ **DNS解析**：域名正确解析到服务器IP
3. ✅ **服务健康**：后端服务和Nginx正常运行
4. ✅ **API功能**：核心API接口可用
5. ✅ **前端访问**：用户界面正常加载
6. ✅ **代理配置**：前端Nginx正确转发API请求
7. ✅ **性能基准**：响应时间在可接受范围内

### 测试环境
- **前端服务器**: `47.115.168.107`
- **后端服务器**: `1.14.202.161:5200`
- **后端域名**: `api.genz.ltd`
- **前端域名**: `szbolent.cn` (备案后启用)

## 🚀 快速开始

### 1. 执行冒烟测试

```bash
# 进入项目目录
cd /Users/jason/Projects/looma-zervi

# 给脚本执行权限
chmod +x scripts/smoke_test.sh

# 运行冒烟测试
./scripts/smoke_test.sh
```

### 2. 测试结果解读

测试脚本会输出彩色标记的结果：
- ✅ 绿色：测试通过
- ⚠️ 黄色：警告（性能较慢但仍可接受）
- ❌ 红色：测试失败

### 3. 预期输出

成功情况下会看到类似输出：
```
===========================================================================
🚀 Looma-Zervi 生产环境冒烟测试
===========================================================================
测试时间: 2026-07-09 11:46:00
测试环境: 生产环境
===========================================================================

📡 阶段1: 网络连通性测试
---------------------------------------------------------------------------
ℹ️ 测试: 前端服务器可达性 (47.115.168.107)
✅ 通过: 前端服务器可达性 (47.115.168.107)
...

📊 测试结果汇总
===========================================================================
总测试数: 17
通过测试: 17
失败测试: 0

🎉 所有冒烟测试通过！系统运行正常。
```

## 🔧 测试脚本详解

### 脚本位置
`scripts/smoke_test.sh`

### ServBay 认钱认人实库冒烟（本机）
在 `backend/` 下执行：`python scripts/smoke_servbay_money_identity.py`（需已有 `data/looma.db`；退出码 0=PASS，1=断言 FAIL，2=库缺失/路径不符/purge 未清干净）。脚本只清理 `@servbay-smoke.local` 账号，开跑前后+异常 finally 清；与 pytest tempfile 无关。

### 测试阶段说明

#### 阶段1: 网络连通性测试
1. **前端服务器可达性** - 检查 `47.115.168.107` 的HTTP访问
2. **后端服务器可达性** - 检查 `1.14.202.161` 的ICMP连通性
3. **后端应用端口开放** - 检查 `5200` 端口是否监听
4. **后端Nginx端口开放** - 检查 `80` 端口是否监听

#### 阶段2: DNS解析测试
5. **API域名DNS解析** - 验证 `api.genz.ltd` 解析到 `1.14.202.161`
6. **域名解析到正确IP** - 使用 `dig` 命令验证解析

#### 阶段3: 服务健康检查
7. **后端健康检查端点** - 直接访问 `:5200/health`
8. **域名健康检查** - 通过域名访问 `/health`
9. **Nginx代理健康检查** - 验证Nginx代理配置

#### 阶段4: API功能测试
10. **诗词随机查询API** - 测试核心业务接口
11. **API根目录信息** - 验证API文档端点
12. **前端代理配置测试** - 验证前端Nginx `/v1/` 转发

#### 阶段5: 性能基准测试
13. **健康检查响应时间** - 目标 < 1秒
14. **诗词API响应时间** - 目标 < 2秒

#### 阶段6: 前端功能测试
15. **前端首页访问** - 验证HTTP 200状态码
16. **前端CSS资源加载** - 验证静态资源访问
17. **前端JS资源加载** - 验证JavaScript加载

## 🐛 故障排查指南

### 常见问题及解决方案

#### 问题1: 前端服务器不可达
```bash
# 检查服务器状态
ping 47.115.168.107

# 检查防火墙规则
ssh root@47.115.168.107 "ufw status"

# 检查Nginx服务
ssh root@47.115.168.107 "systemctl status nginx"
```

#### 问题2: API域名解析失败
```bash
# 检查DNS解析
nslookup api.genz.ltd
dig api.genz.ltd

# 临时使用IP访问测试
curl http://1.14.202.161:5200/health
```

#### 问题3: 后端服务无响应
```bash
# 登录后端服务器
ssh root@1.14.202.161

# 检查应用进程
ps aux | grep gunicorn
systemctl status looma-backend

# 检查应用日志
tail -f /var/log/looma-backend.log

# 重启服务
systemctl restart looma-backend
```

#### 问题4: Nginx代理失败
```bash
# 检查Nginx配置
ssh root@47.115.168.107 "nginx -t"

# 检查Nginx日志
ssh root@47.115.168.107 "tail -f /var/log/nginx/error.log"

# 重启Nginx
ssh root@47.115.168.107 "systemctl restart nginx"
```

#### 问题5: 前端代理转发失败
```bash
# 检查前端Nginx配置
ssh root@47.115.168.107 "grep -A 10 'location /v1/' /etc/nginx/sites-available/*"

# 测试代理转发
curl -v http://47.115.168.107/v1/poetry/random?count=1
```

## 📊 性能基准

### 响应时间标准
| 测试项 | 优秀 | 良好 | 警告 | 严重 |
|--------|------|------|------|------|
| 健康检查 | < 500ms | < 1s | 1-2s | > 2s |
| 诗词API | < 1s | < 2s | 2-3s | > 3s |
| 前端加载 | < 2s | < 3s | 3-5s | > 5s |

### 监控指标
```bash
# 实时监控命令
watch -n 5 'curl -s -o /dev/null -w "健康检查: %{time_total}s\n" http://api.genz.ltd/health'

# 批量性能测试
for i in {1..10}; do
    curl -s -o /dev/null -w "%{time_total}\n" http://api.genz.ltd/v1/poetry/random?count=1
done | awk '{sum+=$1} END {print "平均响应时间:", sum/NR "s"}'
```

## 🔄 自动化集成

### 1. CI/CD集成
```yaml
# GitHub Actions 示例
name: Smoke Test
on: [push]
jobs:
  smoke-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Smoke Test
        run: ./scripts/smoke_test.sh
```

### 2. 定时任务
```bash
# 每天凌晨2点执行
0 2 * * * cd /Users/jason/Projects/looma-zervi && ./scripts/smoke_test.sh >> /var/log/looma-smoke-test.log 2>&1
```

### 3. 告警配置
```bash
# 测试失败时发送告警
if ! ./scripts/smoke_test.sh; then
    # 发送邮件通知
    echo "冒烟测试失败！" | mail -s "Looma系统告警" admin@example.com
    # 发送Slack/钉钉通知
    curl -X POST -H 'Content-type: application/json' \
         --data '{"text":"🚨 Looma冒烟测试失败！"}' \
         https://hooks.slack.com/services/...
fi
```

## 📝 测试记录

### 测试执行记录表
| 测试时间 | 测试结果 | 失败项 | 负责人 | 备注 |
|----------|----------|--------|--------|------|
| 2026-07-09 11:46 | ✅ 全部通过 | 无 | Jason | 首次冒烟测试 |
| 2026-07-08 09:30 | ⚠️ 1项警告 | 响应时间>2s | Jason | 优化后恢复正常 |
| 2026-07-07 14:20 | ❌ 3项失败 | DNS解析失败 | Jason | DNS配置问题已修复 |

### 性能趋势图
```
响应时间趋势（过去7天）：
健康检查:  ▁▂▃▄▅▆▇ (平均: 320ms)
诗词API:   ▁▂▃▄▅▅▆ (平均: 1.2s)
前端加载:  ▁▂▃▃▄▅▅ (平均: 2.1s)
```

## 🛠️ 维护指南

### 1. 测试脚本更新
当系统架构变更时，需要更新测试脚本：
- 添加新的API端点测试
- 更新服务器地址
- 调整性能阈值

### 2. 环境变量配置
```bash
# 可以在执行时指定环境变量
export API_BASE_URL=http://api.genz.ltd
export FRONTEND_URL=http://47.115.168.107
./scripts/smoke_test.sh
```

### 3. 自定义测试项
```bash
# 添加自定义测试
echo "自定义测试: 特定业务功能"
curl -s "http://api.genz.ltd/v1/specific-endpoint" | grep -q "expected_pattern"
```

### 4. 测试报告生成
```bash
# 生成HTML报告
./scripts/smoke_test.sh > smoke-test-report-$(date +%Y%m%d).html

# 生成JSON格式报告
./scripts/smoke_test.sh | jq -R -s 'split("\n")' > smoke-test-$(date +%Y%m%d).json
```

## 🚨 紧急响应

### 测试失败应急流程
1. **立即检查**：运行详细诊断命令
2. **通知团队**：通过预定渠道通知相关人员
3. **回滚决策**：根据失败严重性决定是否回滚
4. **根本原因分析**：记录问题并分析原因
5. **预防措施**：更新监控和告警规则

### 紧急联系人
| 角色 | 负责人 | 联系方式 | 职责 |
|------|--------|----------|------|
| 系统运维 | Jason | 待定 | 服务器故障处理 |
| 后端开发 | Jason | 待定 | API问题排查 |
| 前端开发 | 待定 | 待定 | 前端问题排查 |
| 产品经理 | 待定 | 待定 | 业务影响评估 |

---

## 📈 附录

### A. 测试覆盖率
- 网络层: 100%
- 服务层: 100% 
- API层: 核心功能100%
- 前端层: 基础功能100%

### B. 测试频率建议
- **每次部署后**: 立即执行
- **每日定时**: 凌晨2点自动执行
- **重大变更前**: 预发布环境执行
- **故障恢复后**: 验证恢复效果

### C. 扩展测试建议
1. **压力测试**: 使用k6进行并发测试
2. **安全测试**: OWASP基础安全检查
3. **兼容性测试**: 多浏览器兼容性
4. **监控集成**: 与Prometheus/Grafana集成

### D. 相关文档
- [系统架构文档](./CURRENT_SYSTEM_ARCHITECTURE.md)
- [部署指南](./DEPLOYMENT_GUIDE.md)
- [监控配置](./MONITORING_SETUP.md)

---

**文档状态**: ✅ 当前有效 · 🔄 持续更新 · 🧪 测试指南  
**最后验证时间**: 2026-07-09 11:46  
**验证结果**: 冒烟测试脚本就绪，可立即执行