# cutover-test — 摘块安全门禁

> 用于验证 [MULTI_REPO_PUBLISH_FEDERATION.md](../../docs/MULTI_REPO_PUBLISH_FEDERATION.md) §2 的
> 「摘除 genz.ltd / www.genz.ltd serve 端」这一步**不会误伤 api 与 tspace**。

---

## 它证明什么

**摘掉 nginx 里 `genz.ltd` / `www.genz.ltd` 的 server 块之后：**

1. `api.genz.ltd` 的 `/health` 仍然 200；
2. `api.genz.ltd` 的 `/v1/payment/webhook/*` 路径**还在**（收银链路不被切断）；
3. `tspace.genz.ltd` 不受影响，仍然 200；
4. `genz.ltd` / `www.genz.ltd` 落 catch-all → **404 Unknown host**（不再有营销壳）。

## 它不证明什么

- ❌ 不代替**真 Flask 后端**（stub 只回固定 JSON，不验签、不落库）；
- ❌ 不代替**真 SaaS 构建产物**（tspace 用的是占位 HTML）；
- ❌ 不代替 **HTTPS :443** 行为（本装置是 HTTP-only，对应 Cloudflare Flexible 回源 :80）；
- ❌ 不代替 **DNS 真实切换**（不碰 Cloudflare）。

---

## 探测矩阵

| # | 探测 | Host | 期望 |
|---|------|------|------|
| 1 | `GET /health` | `api.genz.ltd` | 200 `{"status":"ok"}`（stub ok） |
| 2 | `GET /` | `api.genz.ltd` | 404 `Use /v1`（**没有营销壳**） |
| 3 | `POST /v1/payment/webhook/stripe` | `api.genz.ltd` | **200**（路径还在） |
| 4 | `GET /` | `tspace.genz.ltd` | 200（tspace stub） |
| 5 | `GET /` | `genz.ltd` | **404 Unknown host**（裸域块已摘） |
| 6 | `GET /` | `www.genz.ltd` | **404 Unknown host**（裸域块已摘） |

---

## 运行

### macOS / Linux

```bash
bash scripts/cutover-test/run-test.sh
```

可选覆盖：

```bash
NGINX_BIN=/path/to/nginx PYTHON_BIN=/path/to/python3 \
NGINX_PORT=18080 STUB_PORT=15200 \
bash scripts/cutover-test/run-test.sh
```

nginx 自动查找顺序：`$NGINX_BIN` → `PATH` → `/Applications/ServBay/sbin/nginx` →
`/opt/homebrew/bin/nginx` → `/usr/local/bin/nginx` → `/usr/sbin/nginx`。

### Windows / ServBay

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\cutover-test\run-test.ps1
```

可选参数：`-NginxPort 18080` `-StubPort 15200` `-NginxExe <nginx.exe>` `-PythonExe <python.exe>`。
nginx 自动查找：`-NginxExe` → `C:\ServBay\packages\nginx\nginx.exe` → `C:\ServBay\bin\nginx\nginx.exe` → `PATH`。

> **不影响 ServBay 自身的 80/443。** 装置用独立端口（默认 nginx 18080 / stub 15200），
> 结束时自动停止自己起的进程。

---

## 装置构成

| 文件 | 作用 |
|------|------|
| `nginx-cutover-http.conf` | 摘块后的 HTTP-only 配置**模板**（含 `__WORK__` 等占位符） |
| `stub_api.py` | 顶替 Flask :5200 的最小 stub（零依赖，仅标准库） |
| `run-test.sh` | macOS / Linux runner（渲染 → 起 stub → 起 nginx → 断言 → 清理） |
| `run-test.ps1` | Windows / ServBay runner（同口径） |
| `.generated/` | 运行时产物（渲染后的 nginx.conf、mime.types、日志）— **已 gitignore** |

---

## 前置断言（装置自身防漂移）

runner 在起服务**之前**会跑两条断言，防止装置和真配置脱节：

| 断言 | 内容 | 失败含义 |
|------|------|----------|
| **A1** | `docker/nginx.conf` 与 `nginx-vultr.conf` 里不得有 `server_name` 严格等于 `genz.ltd` / `www.genz.ltd` | 裸域块被恢复了 → 错链回归 |
| **A2** | `nginx-cutover-http.conf` 的 Host 集合 == `docker/nginx.conf` 的 Host 集合 | 改了真配置忘了同步模板 → **装置漂移，预演结论无效** |
| **A3** | 两份**真配置本身**过 `nginx -t`（把 `include` 指到本地 `mime.types`、摘掉 ssl）+ 大括号配对计数 | 删 server 块时改坏了配置结构（典型事故：多/少一个 `}`） |

> A3 对真配置做校验，而不是只测预演模板 —— 因为「摘块」这个动作的事故形态正是
> 破坏原文件结构，光测模板抓不到。

> A1 按**整 token** 比对，所以 `api.genz.ltd` 不会被误判为裸域。

改了 `docker/nginx.conf` 的 `server_name` 之后，**必须**同步
`nginx-cutover-http.conf`，否则 A2 会拦下并提示差异。

---

## 清理

runner 退出时（含失败与 Ctrl+C）会：

- 停止自己起的 nginx 与 stub 进程；
- 端口（18080 / 15200）释放。

`.generated/` 保留到最后一次运行，便于看日志；下次运行开头会整目录重建。

---

## 验收证据（2026-09-18）

装置的两次实跑（`run-test.sh` / `run-test.ps1` 是同一套断言的两种宿主实现）：

| 宿主 | nginx | 结果 |
|------|-------|------|
| macOS（ServBay `/Applications/ServBay/sbin/nginx`） | 18080 | **全绿**（A1/A2/A3 + 6/6 Host 探测），可复现单次干净通过 |
| Windows（ServBay `packages\nginx\nginx.exe`） | 18080 | 6/6 Host 探测**观察通过**；该次进程以 exit 1 结束，原因是操作者在跑完后手工停掉 18080 打断 runner，**因此没有一份干净的整跑产物** → 记为「已观察、待补干净复跑」，不当「全绿」引用 |

macOS 一次干净通过的关键行（照抄自运行日志）：

```text
PASS  nginx.conf 无 genz.ltd / www.genz.ltd server_name
PASS  nginx-vultr.conf 无 genz.ltd / www.genz.ltd server_name
PASS  预演配置 Host 集合与 docker/nginx.conf 一致   _ api.genz.ltd tspace.genz.ltd
PASS  nginx.conf nginx -t 通过（braces 27/27）
PASS  nginx-vultr.conf nginx -t 通过（braces 25/25）
PASS  api /health → 200 stub ok  200
PASS  api / → 404 Use /v1（无营销壳）  404
PASS  api POST /v1/payment/webhook/stripe → 200  200
PASS  tspace / → 200 tspace stub  200
PASS  genz.ltd / → 404 Unknown host（块已摘）  404
PASS  www.genz.ltd / → 404 Unknown host（块已摘）  404
全绿：摘块不切 api webhook，不误伤 tspace，裸域落 catch-all。
```

> 真机变更**不在**本装置范围内：本装置只证明「摘块后配置结构与分流正确」。
> 真机落地是合 main 之后的**手动步骤**（scp 改后的 `nginx-vultr.conf` → `nginx -t` → `systemctl reload nginx`）。

---

## 关联

- 口径：[docs/MULTI_REPO_PUBLISH_FEDERATION.md](../../docs/MULTI_REPO_PUBLISH_FEDERATION.md)
- 被摘的 serve 端：`docker/nginx.conf` · `nginx-vultr.conf` · `scripts/deploy-overseas.sh` 第 7 步 · `.github/workflows/deploy-overseas.yml`
- 生产侧冒烟（**不同东西**，不要混）：`scripts/smoke_test.sh`（打公网 api.genz.ltd）
