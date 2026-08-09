/**
 * Lightweight SVG empty-state art (no PNG delivery yet).
 * Swap to /brand/illustrations/tsaas/* when designer assets land.
 */
type BrandEmptyArtProps = {
  variant?: "candidates" | "generic";
  size?: number;
  className?: string;
};

export default function BrandEmptyArt({
  variant = "generic",
  size = 160,
  className,
}: BrandEmptyArtProps) {
  if (variant === "candidates") {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 160 160"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={className}
        aria-hidden
      >
        <circle cx="80" cy="80" r="72" fill="var(--color-primary-light)" opacity="0.55" />
        <rect
          x="36"
          y="48"
          width="88"
          height="72"
          rx="12"
          fill="var(--color-bg-card)"
          stroke="var(--color-border)"
          strokeWidth="2"
        />
        <circle cx="62" cy="78" r="12" fill="var(--color-primary)" opacity="0.9" />
        <path
          d="M46 104c2.5-10 9-16 16-16s13.5 6 16 16"
          stroke="var(--color-primary)"
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
          opacity="0.85"
        />
        <circle cx="104" cy="74" r="10" fill="var(--color-primary)" opacity="0.55" />
        <path
          d="M90 100c2-8 7-13 14-13s12 5 14 13"
          stroke="var(--color-primary)"
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
          opacity="0.5"
        />
        <path
          d="M72 40c8-14 24-14 32 0"
          stroke="var(--color-primary)"
          strokeWidth="2.5"
          strokeLinecap="round"
          fill="none"
          opacity="0.45"
        />
        <circle cx="80" cy="34" r="4" fill="var(--color-primary)" opacity="0.7" />
      </svg>
    );
  }

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 160 160"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden
    >
      <circle cx="80" cy="80" r="72" fill="var(--color-primary-light)" opacity="0.5" />
      <rect
        x="44"
        y="52"
        width="72"
        height="56"
        rx="10"
        fill="var(--color-bg-card)"
        stroke="var(--color-border)"
        strokeWidth="2"
      />
      <path
        d="M56 74h48M56 88h32"
        stroke="var(--color-primary)"
        strokeWidth="3"
        strokeLinecap="round"
        opacity="0.7"
      />
    </svg>
  );
}
