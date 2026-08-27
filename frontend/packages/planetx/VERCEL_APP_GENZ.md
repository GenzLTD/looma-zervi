# PlanetX → app.genz.ltd（Vercel）部署备忘

## Vercel 项目设置（方案 B）

| 项 | 值 |
|---|---|
| Root Directory | `frontend/packages/planetx` |
| Framework Preset | Vite（或 Other） |
| Node.js | 20+ |
| Install / Build / Output | 由本目录 `vercel.json` 接管 |
| Production Domain | `app.genz.ltd` |

## 必填环境变量

| Name | Value | Environment |
|---|---|---|
| `VITE_API_BASE` | `https://api.genz.ltd` | Production（Preview 可用同一值） |

> Vercel 上没有 Nginx 同域反代，**不要**把 `VITE_API_BASE` 留空。

## 本地验证生产构建

```bash
cd frontend
VITE_API_BASE=https://api.genz.ltd pnpm --filter @looma/planetx build
# 产物: packages/planetx/dist
```

## 验收

1. `https://app.genz.ltd` 标题接近「PlanetX — Career Growth Partner」（非旧「星际人格测试」内联页）
2. 浏览器 Network：请求打到 `https://api.genz.ltd/v1/...`
3. 登录 / 测评主路径可用
