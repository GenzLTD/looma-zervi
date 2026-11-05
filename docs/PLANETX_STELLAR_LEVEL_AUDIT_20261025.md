# PlanetX「星际等级」体系 · 本机盘点

> 2026-10-25T12:18:46Z · Mac 侧实测（grep / 逐行读源码 / 数值模拟，无转述）
> 范围：`~/Projects/PlanetX`、`~/Projects/looma-zervi`、`~/Projects/Vultr-Genzltd`

---

## 〇、一句话结论

**有，而且是一整套：文档 + 前端 + 后端三层齐全。** 但它有两个独立于你「一套契约」主线之外的真问题：

1. 🔴 **前后端算出了两个等级** —— 同一个用户的等级在前端和后端的取值不同，最多差 2 级，称号也会变。
2. ⚠️ **它和会员 tier（free/supporter/pro）零交集**，却共用同一个词 `level` 指代完全不同的东西。

---

## 一、资产清单

### 文档层（3 份，`~/Projects/PlanetX/`）

| 文件 | 相关段落 |
|---|---|
| `PlanetX-T空间_市场调研与竞品分析.md` | `:119/121/271/278/332/476/491/556/565/587` —— 「星际人格测试」定为 **P0**（理由：MBTI 是 GEN-Z 最大社交货币、裂变入口）；「星际 IP = 星球/登陆/GEN-Z 精神符号」列为中壁垒 |
| `PlanetX-T空间_缺失要素分析.md` | `:86/87/136/187` —— 明确需要 `/v1/personality/*`；个人主页是求职者的「星球」 |
| `PlanetX-T空间_项目组落地执行方案.md` | `:38/165/169/170/176` —— Sprint 2 排期：星际人格测试页 8h + 分享卡片 4h |

### 前端层（1 个文件，2506 行）

`PlanetX/index.html` —— **单文件内联实现**，97 KB，标题就是「PlanetX · 星际人格测试 | 找到你的星球身份」。
（同目录 `narrative.html` / `demo.html` / `index-tatha.html` / `auth.html` 里 **XP/Lv. 命中数为 0**，等级逻辑只在这一份。）

### 后端层

`looma-zervi/backend/src/api/routes/game_routes.py` —— 7+ 个 `/v1/game/*` 接口。
前端 `API_BASE` 指向 **Looma 后端**（`index.html:879-890`）：

| 环境 | API_BASE |
|---|---|
| `genz.ltd` / `vercel.app` | `https://api.genz.ltd` |
| localhost / 127.0.0.1 | `https://api.servbay.host`（注释写"Looma 由 `backend/dev.sh` 起在 :5200"） |
| 大陆自托管 | 同源相对路径（nginx 把 `/v1/` 反代到同机 Looma） |

---

## 二、这套体系到底定义了什么

### 称号五档（`getRankName`，`index.html:1267-1273`）

| level | 称号 |
|---|---|
| ≤ 3 | 星际新兵 |
| ≤ 6 | 星域探索者 |
| ≤ 10 | 银河领航员 |
| ≤ 15 | 星际指挥官 |
| > 15 | 宇宙传奇 |

### 身份三选（`index.html:616-633`）

星际探索者（找星球轨道）／舰队（3 人成团探索星域）／星际漫游者（星球间漂流）。

### 任务与 XP 奖励（`index.html:689-720`）

| 任务 | XP | 解锁物 |
|---|---|---|
| 星际人格测试 | +50 | 专属星球身份 |
| 组队建舱 | +80 | 隐藏星图 |
| 完成匹配 | +100 | 匹配星图 |
| 邀请好友 | +30 | 额外能量 |

### 等级路径（文件末尾 `index.html:2500` 的彩蛋）

```
Lv.1 星际人格测试 → Lv.2 组建舰队 → Lv.3 星际匹配 → Lv.4 信号传播 → Lv.5 C2B HR 画像裂变
```

### 后端接口（`game_routes.py:6-19`）

`/v1/game/profile` · `/profile-sync` · `/mission-complete` · `/match` · `/fleet/create` · `/fleet/join` · `/fleet/mine` · `/fleet/leave` · `/signal-ingest`（另有 HarmonyOS 元服务的 `/start` `/answer` `/result` `/history`）。

数据落 `game_profiles` 表，含 `xp`、`level`、`xp_to_next`、`missions_completed`。
**登录用户持久化到后端；未登录无任何 localStorage**（我搜过，全文件零 `localStorage`）⇒ 刷新即丢。

---

## 三、🔴 核心问题：前后端是两个不同的等级模型

### 后端（权威来源）

```python
# game_routes.py:44-47
def _calculate_level(xp: int) -> int:
    """Level formula: level = floor(sqrt(xp / 100)) + 1."""
    return int(math.sqrt(xp / 100)) + 1 if xp > 0 else 1
```

**level 由「累计总 XP」的平方根决定。** 并且后端不信任自己存的 level 列，`/profile` 每次都重算：

```python
# game_routes.py:223-227
computed_level = _calculate_level(profile["xp"])
if computed_level != profile["level"]:
    db.update_level(g.user_id, computed_level)
```

下一级还需多少：`xp_to_next = max(100, (level ** 2) * 100 - xp)`（`:234`）—— 同样是总 XP 口径。

### 前端（另一套）

```javascript
// index.html:1250-1265
function addXP(amount) {
  STATE.xp += amount;
  while (STATE.xp >= STATE.xpToNext) {
    if (STATE.xpToNext <= 0) break;      // Bugfix: guard against infinite loop
    STATE.xp -= STATE.xpToNext;          // ← 跨级后 XP 清零
    STATE.level++;
    STATE.xpToNext = Math.floor(STATE.xpToNext * 1.5);   // ← 1.5 倍递增
    showAchievement('⬆️ 升级！', `你已晋升为 Lv.${STATE.level} · ${getRankName(STATE.level)}`);
  }
}
```

**level 由「跨级递减后的余量」逐级累乘决定。** `STATE.xp` 是**本级内** XP，跨级就减去。

### 两个模型的后果

**① 语义错配**：后端返回的 `total_xp` 被直接赋给前端的"本级 XP"变量（`index.html:1066`）：

```javascript
if (data.total_xp !== undefined) STATE.xp = data.total_xp;   // 总 XP → 本级 XP
```

**② 数值错配**（我用两套公式做了相同输入的对照）：

| 累计 XP | 后端 level | 后端称号 | 前端 level | 前端称号 | 差 |
|---:|---:|---|---:|---|---:|
| 100 | 2 | 星际新兵 | 2 | 星际新兵 | 0 |
| 250 | 2 | 星际新兵 | **3** | 星际新兵 | **-1** ⚠️ |
| 475 | 3 | 星际新兵 | **4** | **星域探索者** | **-1** ⚠️ |
| 812 | 3 | 星际新兵 | **5** | **星域探索者** | **-2** ⚠️ |
| 1318 | 4 | 星域探索者 | **6** | 星域探索者 | **-2** ⚠️ |
| 2500 | 6 | 星域探索者 | **7** | **银河领航员** | **-1** ⚠️ |

升级门槛对比（达到该级所需**累计** XP）：

| level | 后端 | 前端 |
|---:|---:|---:|
| 2 | 100 | 100 |
| 3 | 400 | **250** |
| 4 | 900 | **475** |
| 5 | 1600 | **812** |
| 6 | 2500 | **1317** |

⇒ **前端升级比后端快一倍左右**，只要 XP 一过 250 就开始分叉。

### 可复现的用户可见症状

1. **等级回退**：前端升到 Lv.3 后刷新页面，`/v1/game/profile` 返回后端的 Lv.2 ⇒ 用户看到自己的等级**往回掉**。
2. **XP 条跳变**：登录后 hydrate，`STATE.xp` 从"本级余量"被替换成"累计总量"，进度条百分比突跳（例如 `30/150` → `130/270`）。
3. 那行 `(STATE.xpToNext <= 0) break; // Bugfix: guard against infinite loop` 说明**已经有人踩过**由这两套模型叠出来的循环。

---

## 四、⚠️ 它和会员 tier 完全是两回事，但共用同一个词

**`game_routes.py` 全文搜不到任何 `tier` / `membership` / `entitlement`** —— 星际等级和付费会员**零交叉、零联动**。

两套「等级」各自独立存在：

| | 星际等级 | 会员 tier |
|---|---|---|
| 取值 | Lv.1…∞（连续） | `free` / `supporter` / `pro`（离散） |
| 来源 | 做任务攒 XP | 付费订阅（Stripe / Apple IAP / HMS IAP） |
| 存储 | `game_profiles.xp` / `.level` | `users.tier` + 订阅表 |
| 仲裁 | 无 | **entitlement 仲裁层**（昨天那套 `tier = max(...)`） |
| 跨区 | 无 region 概念 | 有 `users.region`（刚加的区域维度） |

**而坑在于同一个词 `level` 指两种东西**：

- `game_routes.py` 里 `level` = 星际等级（数字）
- `card_routes.py:55-56` 里 `"level": _tier_display(user.get("tier","free"))` —— 这里的 `level` 其实是 **tier 的展示字符串**

> 同一个字段名，一个地方是 int 的游戏等级，另一个地方是 str 的会员档位名。

这正是你「一套契约」主线要防的那类东西：不是两处都想错了，而是**两处各自都对，凑到一起就不可读**。

---

## 五、建议（按优先级）

| 优先级 | 事项 | 理由 |
|---|---|---|
| **P0** | 二选一作为唯一权威：**建议留后端 sqrt 公式**，前端删掉 `addXP` 里的自算逻辑，只做展示 | 等级将来要用于配额/权益时，必须是服务端说了算；前端自算是典型的"可以伪造" |
| **P0** | 前端不再用 `total_xp` 覆盖 `STATE.xp`，改为接受后端的 `xp`（本级）/ `xp_to_next` | 一行改动，消掉等级回退和进度条跳变 |
| P1 | 给这套也做一份契约（`game.v1.json`），把称号表、任务奖励表、XP 曲线写进去 | 现在称号是硬编码在 JS 的 if-else 里，改称号要改前端；与之前说的「tier 定档双真源」同病 |
| P1 | 决定是否让星际等级与会员 tier 打通（如：pro 会员 XP 加成 / 称号前缀） | 不打通就明确写文档"这是两套独立体系"，并在代码里把 `level` 改名避免歧义 |
| P2 | 把 `/v1/game/*` 纳入合适的仓库与 CI | 前端在 `PlanetX/`，后端在 `looma-zervi/`，两者目前没有互相校验的机制 |

---

## 六、核查方法与边界

**实测项**：逐文件 grep 中文关键词定位 → 读 `index.html` 的 `getRankName` / `addXP` / `API_BASE` / `applyGameProfile` 全文 → 在三个仓库 grep 后端路由 → 读 `game_routes.py:44-47`（level 公式）、`:184-234`（profile 组装）、`:275-325`（mission-complete）→ 用 Python 复现两套公式做数值对照。

**边界**：没有起服务、没有发 HTTP 请求。第三节的数值对照是**按源码公式复现**，不是抓包观测；第三节的可复现症状是静态推导（logger 与后端的 hydrate 路径已读到，但没实跑）。另外 `xp_to_next` 只出现在 profile 读取路径，`mission-complete` 的返回值里没有它——这点值得单独确认是否为有意的省略。

---

## 附录｜归档说明与姊妹篇

入仓位置 `docs/PLANETX_STELLAR_LEVEL_AUDIT_20261025.md`，分支 `audit/planetx-six-domains-20261025`。

**请注意本文档与另一份的分工** —— 两者都谈 PlanetX 的"等级"，但不是同一件事，别合并着读：

| | 本文（星际等级） | `PLANETX_SIX_DOMAINS_DEEP_AUDIT_20261025.md`（六域） |
|---|---|---|
| 讨论对象 | 游戏 XP / 星际称号五档 | 叙事引擎的六个端口、价值印记、Act 1 |
| 结论 | 前后端两套等级公式，最大差 2 级 | 核心机制「价值印记」全代码不可达，DB 0 行 |
| 共同病根 | 同一个：**两处各自都对，合到一起不可读，且没有机制能发现** | 同左 |

还有一处交叉点值得单列，且与当前正在进行的一契约 / 一账本主线直接相关：
**星际等级与会员 tier 之间零交叉**（`game_routes.py` 全文无 `tier` / `membership` / `entitlement`）。
这不一定是缺陷 —— 它更像是**尚未决策**：等级要不要用于配额和权益（如 pro 会员 XP 加成、称号前缀）。
一旦决定打通，这两套体系就必须合进同一个「好的那边真源」机制；若决定不打通，则应把字段名 `level`
改名以消除与会员 tier 展示字段（见 `card_routes.py:55`）的同名歧义。
