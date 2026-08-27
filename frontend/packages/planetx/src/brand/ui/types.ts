/**
 * PlanetX UI component Props type definitions.
 * Internal team uses these interfaces to wire data into components.
 */

// ============================================================
// Button
// ============================================================
export type ButtonVariant = "primary" | "accent" | "outline" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface PlanetXButtonProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  disabled?: boolean;
  loading?: boolean;
  fullWidth?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  children: React.ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
}

// ============================================================
// Card
// ============================================================
export type CardVariant = "default" | "highlight" | "glass";

export interface PlanetXCardProps {
  variant?: CardVariant;
  highlighted?: boolean;
  padding?: "sm" | "md" | "lg";
  onClick?: () => void;
  children: React.ReactNode;
  className?: string;
}

// ============================================================
// Input / TextArea
// ============================================================
export interface PlanetXInputProps {
  value: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  error?: boolean;
  size?: "sm" | "md";
  label?: string;
  helperText?: string;
  type?: "text" | "password" | "email" | "number";
  maxLength?: number;
}

export interface PlanetXTextAreaProps {
  value: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  error?: boolean;
  label?: string;
  helperText?: string;
  rows?: number;
  maxLength?: number;
}

// ============================================================
// XPBar
// ============================================================
export type XPTierColor = "bronze" | "silver" | "gold" | "platinum" | "diamond";

export interface PlanetXXPBarProps {
  level: number;
  xp: number;
  xpToNext: number;
  rankName?: string;
  tier?: XPTierColor;
  size?: "sm" | "lg";
  animate?: boolean;
}

// ============================================================
// LevelBadge
// ============================================================
export type BadgeShape = "circle" | "hexagon" | "diamond";
export type BadgeTier = "bronze" | "silver" | "gold" | "platinum" | "diamond";

export interface PlanetXLevelBadgeProps {
  level: number;
  shape?: BadgeShape;
  tier?: BadgeTier;
  size?: number;
  glowing?: boolean;
  label?: string;
}

// ============================================================
// QuizOptionCard
// ============================================================
export type QuizOptionState = "default" | "selected" | "correct" | "wrong" | "disabled";

export interface PlanetXQuizOptionCardProps {
  label: string;
  description?: string;
  index?: number;
  state?: QuizOptionState;
  onClick?: () => void;
}

// ============================================================
// AchievementPopup
// ============================================================
export interface PlanetXAchievementPopupProps {
  visible: boolean;
  title: string;
  description?: string;
  /** React node or leave default trophy icon */
  icon?: React.ReactNode;
  onClose?: () => void;
}

// ============================================================
// ToastBar
// ============================================================
export type ToastType = "info" | "success" | "warning" | "error";

export interface PlanetXToastBarProps {
  message: string;
  type?: ToastType;
  visible: boolean;
  duration?: number;
  onClose?: () => void;
}

// ============================================================
// Loading
// ============================================================
export interface PlanetXLoadingProps {
  size?: "sm" | "md" | "lg";
  text?: string;
  fullscreen?: boolean;
}

// ============================================================
// StarBackground
// ============================================================
export interface PlanetXStarBackgroundProps {
  starCount?: number;
  color?: string;
  withFloatParticles?: boolean;
}

// ============================================================
// Modal
// ============================================================
export type ModalSize = "sm" | "md" | "lg" | "full";

export interface PlanetXModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  size?: ModalSize;
  showClose?: boolean;
  overlayClickClose?: boolean;
}

// ============================================================
// Dropdown
// ============================================================
export interface DropdownItem {
  value: string;
  label: string;
  icon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  disabled?: boolean;
}

export interface PlanetXDropdownProps {
  trigger: React.ReactNode;
  items: DropdownItem[];
  align?: "left" | "right" | "center";
  width?: string;
  onSelect?: (value: string) => void;
  disabled?: boolean;
}

// ============================================================
// Tabs
// ============================================================
export interface PlanetXTabItem {
  value: string;
  label: string;
  icon?: React.ReactNode;
  badge?: string | number;
}

export interface PlanetXTabsProps {
  items: PlanetXTabItem[];
  activeTab: string;
  onChange?: (value: string) => void;
  variant?: "default" | "pills";
  orientation?: "horizontal" | "vertical";
  fullWidth?: boolean;
}

// ============================================================
// ChatBubble
// ============================================================
export type ChatRole = "user" | "ai";

export interface PlanetXChatBubbleProps {
  role: ChatRole;
  content: string;
  markdown?: boolean;
  timestamp?: string;
  avatar?: string;
  loading?: boolean;
}

// ============================================================
// StreamingText
// ============================================================
export interface PlanetXStreamingTextProps {
  text: string;
  done?: boolean;
  cursorBlink?: boolean;
  speed?: number;
}

// ============================================================
// Tooltip
// ============================================================
export type TooltipPosition = "top" | "bottom" | "left" | "right";

export interface PlanetXTooltipProps {
  children: React.ReactNode;
  content: React.ReactNode;
  position?: TooltipPosition;
  delay?: number;
  maxWidth?: string;
  disabled?: boolean;
}

// ============================================================
// Icon
// ============================================================
export type { PlanetXIconName, PlanetXIconProps } from "./PlanetXIcon";
