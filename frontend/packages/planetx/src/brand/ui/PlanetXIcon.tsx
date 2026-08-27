/**
 * PlanetXIcon — SVG icon component.
 *
 * Props:
 * - name: registry key
 * - size: px (default 20)
 * - color: CSS color (default currentColor → inherit / token)
 * - strokeWidth: default 1.75 (game-feel rounded stroke)
 * - title: optional a11y label (sets role=img)
 */
import { ICON_GLYPHS, type PlanetXIconName } from "./icons/glyphs";

export type { PlanetXIconName };

export interface PlanetXIconProps {
  name: PlanetXIconName;
  size?: number;
  color?: string;
  strokeWidth?: number;
  title?: string;
  className?: string;
  style?: React.CSSProperties;
}

export default function PlanetXIcon({
  name,
  size = 20,
  color = "currentColor",
  strokeWidth = 1.75,
  title,
  className,
  style,
}: PlanetXIconProps) {
  const glyph = ICON_GLYPHS[name];
  if (!glyph) return null;

  return (
    <span
      className={className}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: size,
        height: size,
        color,
        lineHeight: 0,
        ...style,
      }}
    >
      {glyph({ size, strokeWidth })}
    </span>
  );
}
