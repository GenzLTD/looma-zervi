# PlanetX Icon System (P0)

## 结论

Figma 情绪板 `KU7z…` 的「图标风格」区只有**参考位图**，没有可导出的 SVG 组件集。  
因此本仓落地为：

1. `PlanetXIcon`（`name` / `size` / `color`，默认 `currentColor` 吃 token）
2. `icons/glyphs.tsx` 第一批描边图标（可按同名替换设计师 SVG）
3. `EMOJI_TO_ICON` 迁移对照表

## 用法

```tsx
import { PlanetXIcon } from "@looma/planetx/brand/ui";

<PlanetXIcon name="rocket" size={20} color="var(--px-color-accent)" />
```

## 本轮已替换

- `PlanetXToastBar` / `PlanetXAchievementPopup` / `PlanetXButton` loading
- `HubScreen` Tab / 任务 / 时间线 / 退出
- `AuthScreen` 登录/注册/访客按钮
- Storybook：`PlanetX/New Components → IconSystemExample`

## 仍用 emoji 的场景（有意保留或下一轮）

- 人格结果 `personalityType.emoji`（内容数据，非 UI chrome）
- Onboarding 身份卡大图感 emoji（偏插画，属 P3）
- Tspace / SharePanel / FleetPanel 部分文案装饰
