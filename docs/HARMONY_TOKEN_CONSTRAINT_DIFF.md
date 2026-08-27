# HarmonyOS 情绪板 × H1/H2 · Token / 约束 Diff

> **日期：** 2026-08-07  
> **状态：** 分析完成 · **不写入** `planetx` / `saas` tokens（品牌隔离）  
> **源：**
> - 情绪板：[第一期风格设计 · HarmonyOS情绪板](https://www.figma.com/design/KU7zSVEh3Iixw4itYAdZAf/第一期风格设计?node-id=1-945)（`1:945`）
> - 高保真：[8 屏 · H1/H2](https://www.figma.com/design/9cYXttbA4CE3TS6VlgAc33) + 本地 `docs/design-hi-fi/20260729/html/H1_*.html` / `H2_*.html`

---

## 0. 定位（红线）

| 面 | 是什么 | 不是什么 |
|---|---|---|
| 鸿蒙元服务 | PlanetX 在华为系统里的**小卡片 / 免安装入口** | 独立深色 App、T空间控制台 |
| 视觉 | 系统原生浅色：浅灰底 + 白大圆角卡 + 鸿蒙蓝 | 深空紫霓虹、强发光、游戏化装饰 |
| 品牌色 | 橙/紫**小面积**（CTA、图标、选中态） | 大面积品牌铺色抢系统感 |

一期产品 backlog：**元服务真机上架缓做**。本文只出约束与 token 真源，不新建 React `--hm-*` 包。

---

## 1. 情绪板抽出的规范 Token（建议真源）

> 情绪板色块标签有几处笔误（见 §5）。下表以**风格建议正文 + 语义色块 + H1/H2 已落地值**收敛后的「推荐真源」为准。

### 1.1 色彩

| Token（建议名） | 推荐值 | 来源依据 | 用途 |
|---|---|---|---|
| `--hm-color-primary` | `#007DFF` | 风格建议正文「鸿蒙蓝」；H1/H2 `--hm` | 系统主色、主 CTA、进度条、元服务角标底 |
| `--hm-color-primary-soft` | `#E8F2FF` | H1 chip/meta | 选中 chip、角标浅底 |
| `--hm-color-brand-orange` | `#FF7B32` | 情绪板正文品牌橙；接近 H1 `#FF6B35` | 卡片内小 CTA / 选中描边（小面积） |
| `--hm-color-brand-purple` | `#875DEF` | 情绪板辅助紫 | 图标渐变终点、点缀 |
| `--hm-color-success` | `#22C55E` | 情绪板辅助绿 | 成功态（按需） |
| `--hm-color-warning` | `#F59E0B` | 情绪板辅助橙黄 | 警告（按需） |
| `--hm-color-text-t1` | `#182431` | 情绪板 T1 + H1/H2 | 标题/主文 |
| `--hm-color-text-t2` | `#666666` | 情绪板 T2 | 次级文（见 §2 与 H1 gap） |
| `--hm-color-text-t3` | `#999999` | 情绪板 T3 | 更弱说明 |
| `--hm-color-bg-page` | `#F1F3F5` | 情绪板「页面背景」 | 系统页底（负一屏场景） |
| `--hm-color-bg-card` | `#FFFFFF` | 情绪板「卡片背景」 | 服务卡 / 答题卡 |
| `--hm-color-bg-surface` | `#F7F8FA` | H1/H2 `--card` | 次级块（小艺建议条） |
| `--hm-color-divider` | `#E5E5E5` | 情绪板「分割线」 | 分割线 |
| `--hm-color-border` | `#E8ECF2` | H1/H2 | 选项/chip 描边 |
| `--hm-color-on-primary` | `#FFFFFF` | 通用 | 主色上的字 |

### 1.2 字体

| Token | 推荐值 | 用途（情绪板） |
|---|---|---|
| `--hm-font-family` | `"HarmonyOS Sans", "Inter", "Noto Sans SC", sans-serif` | 官方优先，缺字用 Inter + 思源 |
| `--hm-font-size-search` | `18 / 24`（字号/行距 px） | 搜索框、区块小标题 |
| `--hm-font-size-card-title` | `16 / 22` | PlanetX 卡片标题 |
| `--hm-font-size-body` | `14 / 20` | 卡片描述、小艺正文 |
| `--hm-font-size-label` | `12 / 16` | 快捷入口、时间 |
| `--hm-font-size-caption` | `11 / 14` | 元服务角标、极小说明 |

### 1.3 圆角 / 阴影 / 密度

| Token | 推荐值 | 约束 |
|---|---|---|
| `--hm-radius-card` | `16px`～`24px` | 服务卡、建议卡 |
| `--hm-radius-control` | `12px` | 选项行 |
| `--hm-radius-pill` | `20px+` / `9999px` | 搜索胶囊、主按钮 |
| `--hm-radius-icon` | `8px`～`12px` | 品牌小图标 |
| `--hm-shadow-card` | 极轻（例 `0 4px 16px rgba(24,36,49,.05~.08)`） | **禁止**辉光 / 强投影 |
| 信息密度 | 一屏说清「是什么 / 能做什么 / 点哪里」 | 少模块、少文案 |

### 1.4 场景约束（非色值）

1. **嵌入系统**：负一屏 / 小艺建议 / 服务中心卡片，不是全屏游戏壳。  
2. **免安装叙事**：H2 必须保留「即用即走 + 数据同步 PlanetX」信息。  
3. **品牌面积**：橙紫仅图标渐变、选中态、小标签；主 CTA 优先鸿蒙蓝。  
4. **禁止**：深色太空底、Orbitron 游戏标题字、XP 辉光、弹簧弹跳动效作为默认交互。

---

## 2. 对照 H1 / H2（本地 HTML）· Diff

### 2.1 已对齐（可保留）

| 项 | 情绪板 / 约束 | H1 | H2 |
|---|---|---|---|
| 系统主色 | 鸿蒙蓝 | `#007DFF` ✅ | `#007DFF` ✅ |
| 主文色 T1 | `#182431` | ✅ | ✅ |
| 白卡 + 浅底 | 浅色系统感 | 渐变浅底 + 白卡 ✅ | 白底 + 灰条 ✅ |
| 卡片圆角 | 16–24 | `16px` ✅ | `16px` ✅ |
| 搜索/按钮胶囊 | 20px+ | 搜索 `999px`、CTA `24px` ✅ | Next `24px` ✅ |
| 阴影 | 极轻 | 有轻阴影 ✅ | 有轻阴影 ✅ |
| 元服务叙事 | 入口卡 / 免安装 | 「元服务」角标 ✅ | 「免安装体验」+ 同步文案 ✅ |
| 品牌小面积 | 橙紫点缀 | 图标渐变 + 弱描边 ✅ | 选中橙 + 小标签 ✅ |

### 2.2 需要对齐 / 有差距

| 语义 | 情绪板推荐 | H1/H2 现状 | 差距 | 建议 |
|---|---|---|---|---|
| 主色命名一致性 | 正文 `#007DFF`；色块标签曾写 `#145EFF` | `#007DFF` | 情绪板内部不一致 | **以 `#007DFF` 为真源**；色板标签视为笔误 |
| 品牌橙 | `#FF7B32`（正文） | `#FF6B35` | Δ≈偏红 | H1/H2 可收到 `#FF7B32`，或文档注明「可接受 ±」 |
| 品牌紫 | `#875DEF` / 正文 `#AD3BFF` | `#8B5CF6` | 三套并存 | 收敛为 `#875DEF`（辅助色卡） |
| 次级字 T2 | `#666666` | `#99A2B1` | 明显更浅/偏蓝灰 | 系统感跟情绪板用 `#666`；若可读性要冷灰可保留并写进例外 |
| 页面底 | `#F1F3F5` | H1 `#F3F6FB→#fff`；H2 `#fff` | 接近但不统一 | 系统壳用 `#F1F3F5`；答题全屏可用白 |
| 字族 | HarmonyOS Sans → Inter + 思源 | `Noto Sans SC` | 未用官方栈 | HTML 预览可保持 Noto；ArkTS 真机用 HarmonyOS Sans |
| 字号阶梯 | 18/16/14/12/11 | 大致贴近，未成 token 表 | 缺命名体系 | 落地时按 §1.2 建档 |
| H2 主 CTA 色 | 主 CTA 优先鸿蒙蓝 | Next 已是蓝 ✅；选项选中用橙 | 符合「蓝主 / 橙点缀」 | 保持；勿把 Next 改成品牌橙 |
| 情绪板 §05 示意页 | 有大面积紫蓝英雄卡 | H1 更克制（系统卡） | 示意页偏「轻 App」 | **以 H1 系统卡 + 风格正文为准**，§05 仅作版式参考 |

### 2.3 可忽略

| 项 | 原因 |
|---|---|
| 情绪板辅助绿/黄未进 H1/H2 | 当前两屏无 success/warning 场景 |
| 玻璃拟态参考截图 | 气质参考；H1/H2 用白卡+轻阴影已够元服务密度 |
| PlanetX 全量游戏 token（`--px-*`） | 明确不进鸿蒙入口 |

---

## 3. 推荐「未来 ArkTS」最小 Token 表（独立，不进 monorepo UI）

```css
/* 仅文档 / 未来 harmony 仓引用 — 勿合并进 planetx/saas */
:root {
  --hm-color-primary: #007DFF;
  --hm-color-primary-soft: #E8F2FF;
  --hm-color-brand-orange: #FF7B32;
  --hm-color-brand-purple: #875DEF;
  --hm-color-text-t1: #182431;
  --hm-color-text-t2: #666666;
  --hm-color-text-t3: #999999;
  --hm-color-bg-page: #F1F3F5;
  --hm-color-bg-card: #FFFFFF;
  --hm-color-bg-surface: #F7F8FA;
  --hm-color-divider: #E5E5E5;
  --hm-color-border: #E8ECF2;
  --hm-color-on-primary: #FFFFFF;

  --hm-font-family: "HarmonyOS Sans", "Inter", "Noto Sans SC", sans-serif;
  --hm-font-size-search: 18px;
  --hm-font-size-card-title: 16px;
  --hm-font-size-body: 14px;
  --hm-font-size-label: 12px;
  --hm-font-size-caption: 11px;

  --hm-radius-card: 16px;
  --hm-radius-control: 12px;
  --hm-radius-pill: 9999px;
  --hm-shadow-card: 0 4px 16px rgba(24, 36, 49, 0.06);
}
```

---

## 4. 建议改动优先级（仅鸿蒙设计资产 / 未来仓）

| 优先级 | 动作 | 影响 |
|---|---|---|
| **P0** | 锁定主色真源 `#007DFF`；在情绪板修正 `#145EFF` 标签（若可编辑） | 避免双主色 |
| **P1** | H1/H2 HTML：品牌橙/紫收到推荐值；T2 决定跟 `#666` 还是保留冷灰并写进例外 | 预览稿与情绪板一致 |
| **P1** | 字号/圆角按 §1 建成注释表（不必进 React） | ArkTS 开工可抄 |
| **P2** | 情绪板清理错误标签（橙块写 `#F59E0B`、黄块误标 `#875DEF` 等） | 减少下游误读 |
| **P3** | 真机仓再落 `--hm-*`；本期不上架 | 与 backlog「缓」一致 |

---

## 5. 情绪板已知标签噪声（阅读时注意）

从 MCP 结构读到的色块文字与填充不完全一致，例如：

- 主色大块标签出现 `#145EFF`，风格正文写 `#007DFF`
- 橙辅助块填充偏 `#FF8642`，标签写 `#F59E0B`；正文品牌橙又写 `#FF7B32`
- 一块黄色填充标签误写为 `#875DEF`（与紫卡重复）

**裁决规则：** 风格建议正文 + H1/H2 已用值 > 色块上的 hex 标签。

---

## 6. 收口结论

1. 鸿蒙是**第三套场景约束**，不是第三套 Web 品牌包；**不要**并进 `--px-*` / `--color-*`。  
2. H1/H2 整体已落在正确调性（浅色、鸿蒙蓝主 CTA、品牌小面积）；差距主要在**中性灰/品牌橙紫的精确值**和**字族**。  
3. **ArkTS 已落地（2026-08-07）**：`/Users/jason/DevEcoStudioProjects/MyApplication`  
   - `Colors.ets` / `BrandTokens.ets` / `color.json` 真源改为 `#007DFF` + `#FF7B32`  
   - 主 CTA（`PrimaryCTA` / `LmButton` primary / `ServiceEntry` / `GamePage`）→ 鸿蒙蓝  
   - 选项选中仍用品牌橙；Job/Partner/Resume 等 indigo 硬编码页留待下一轮
