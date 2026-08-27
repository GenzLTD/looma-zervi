# release/overseas · Zervi（PlanetX Web+PWA）短板补齐记录

> **日期**：2026-07-13  
> **分支**：`release/overseas`  
> **背景**：团队收口四线，主投 Web+PWA；对照 `MULTI_CLIENT_CX_STRATEGY` / `DUAL_TRACK_ACCEPTANCE_CHECKLIST` 补缺口。

## 盘点结论（补齐前）

| 域 | 状态 |
|----|------|
| G1 genz-web 营销 / 法律 / 定价 | 较齐 |
| API 海外部署文档 | 有 |
| Google 后端 `/v1/auth/google` | 有 |
| PlanetX PWA | **缺** |
| PlanetX Google 登录 UI | **缺** |
| Match Web 演示摩擦（需 3 人解锁 / 共识门控 / 404） | **偏高** |

## 本轮已补

1. **PWA M0/M1**：`public/manifest.webmanifest`、icons、`sw.js`、`registerSW.ts`、`index.html` meta  
2. **Google**：shared-core `AUTH_GOOGLE` + `authApi.google`；AuthScreen GIS（需 `VITE_GOOGLE_CLIENT_ID`）  
3. **Match 演示**：Hub 舰队≥2 可开 match；`?join=` 入队；错误文案；确认按钮信任 `can_complete_mission`  
4. **共识 API 占位**：`GET/POST .../match/consensus|acknowledge` 返回空/noop  
5. **验收清单**：OS-P1-4b/4c + 快照更新  

## 仍待线上 / 配置（代码外）

- [ ] 配置 `VITE_GOOGLE_CLIENT_ID` 并完成 OS-P0-9 E2E  
- [ ] HTTPS 部署 PlanetX 后验证「安装到主屏幕」  
- [ ] Stripe Checkout 回跳 PWA（M3）  
- [ ] 小程序：冻结功能，不跟本轮  

## 本地验

```bash
cd backend && ./dev.sh
cd frontend/packages/planetx && pnpm dev   # :5173
# 可选：VITE_ENABLE_PWA=true 强制注册 SW
# 双账号：A 建舰队复制链接，B 打开 ?join=CODE
```
