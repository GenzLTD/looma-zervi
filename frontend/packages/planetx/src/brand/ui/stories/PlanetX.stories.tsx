/**
 * PlanetX UI Components — Storybook Stories (CSF format).
 * Run: cd frontend && pnpm storybook (see STORYBOOK.md)
 */
import type { Meta, StoryObj } from "@storybook/react";
import {
  PlanetXButton,
  PlanetXCard,
  PlanetXInput,
  PlanetXTextArea,
  PlanetXXPBar,
  PlanetXLevelBadge,
  PlanetXQuizOptionCard,
  PlanetXAchievementPopup,
  PlanetXToastBar,
  PlanetXLoading,
  PlanetXStarBackground,
} from "../index";

// ============================================================
// Button
// ============================================================
const meta: Meta<typeof PlanetXButton> = {
  title: "PlanetX/Button",
  component: PlanetXButton,
  tags: ["autodocs"],
  args: { children: "星际出发" },
};
export default meta;
type Story = StoryObj<typeof PlanetXButton>;

export const Primary: Story = { args: { variant: "primary", children: "主要按钮" } };
export const Accent: Story = { args: { variant: "accent", children: "荧光绿按钮" } };
export const Outline: Story = { args: { variant: "outline", children: "描边按钮" } };
export const Ghost: Story = { args: { variant: "ghost", children: "幽灵按钮" } };
export const Danger: Story = { args: { variant: "danger", children: "危险按钮" } };
export const Sizes: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
      <PlanetXButton size="sm">Small</PlanetXButton>
      <PlanetXButton size="md">Medium</PlanetXButton>
      <PlanetXButton size="lg">Large</PlanetXButton>
    </div>
  ),
};
export const Loading: Story = { args: { loading: true, children: "加载中" } };
export const Disabled: Story = { args: { disabled: true, children: "禁用" } };

// ============================================================
// Card
// ============================================================
export const CardDefault: StoryObj<typeof PlanetXCard> = {
  render: () => <PlanetXCard>Card 内容</PlanetXCard>,
};
export const CardHighlight: StoryObj<typeof PlanetXCard> = {
  render: () => <PlanetXCard highlighted>高亮 Card</PlanetXCard>,
};

// ============================================================
// Input
// ============================================================
export const InputDefault: StoryObj<typeof PlanetXInput> = {
  args: { placeholder: "输入你的星际代号", label: "代号", value: "" },
};
export const InputError: StoryObj<typeof PlanetXInput> = {
  args: { label: "邮箱", value: "bad", error: true, helperText: "邮箱格式不正确" },
};

// ============================================================
// XPBar
// ============================================================
export const XPBarDefault: StoryObj<typeof PlanetXXPBar> = {
  args: { level: 7, xp: 340, xpToNext: 500, rankName: "探索者" },
};

// ============================================================
// LevelBadge
// ============================================================
export const LevelBadgeCircle: StoryObj<typeof PlanetXLevelBadge> = {
  args: { level: 10, tier: "gold", glowing: true },
};
export const LevelBadgeHexagon: StoryObj<typeof PlanetXLevelBadge> = {
  args: { level: 25, shape: "hexagon", tier: "diamond" },
};

// ============================================================
// QuizOptionCard
// ============================================================
export const QuizOptionDefault: StoryObj<typeof PlanetXQuizOptionCard> = {
  args: { label: "我喜欢探索未知领域", index: 0 },
};
export const QuizOptionSelected: StoryObj<typeof PlanetXQuizOptionCard> = {
  args: { label: "我喜欢分析数据", index: 1, state: "selected" },
};
export const QuizOptionCorrect: StoryObj<typeof PlanetXQuizOptionCard> = {
  args: { label: "团队合作", index: 2, state: "correct" },
};

// ============================================================
// AchievementPopup
// ============================================================
export const Achievement: StoryObj<typeof PlanetXAchievementPopup> = {
  args: {
    visible: true,
    title: "首次升空！",
    description: "完成第一次人格测试",
    icon: undefined,
  },
};

// ============================================================
// ToastBar
// ============================================================
export const ToastSuccess: StoryObj<typeof PlanetXToastBar> = {
  args: { message: "操作成功！", type: "success", visible: true },
};
export const ToastError: StoryObj<typeof PlanetXToastBar> = {
  args: { message: "网络错误，请重试", type: "error", visible: true },
};

// ============================================================
// Loading
// ============================================================
export const LoadingDefault: StoryObj<typeof PlanetXLoading> = {
  args: { text: "加载中..." },
};
