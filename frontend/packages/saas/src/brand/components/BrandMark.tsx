/**
 * TSpace logomark — geometric “T” in brand primary.
 * Used in chrome (sidebar / hero) so the product reads as TSpace, not a generic SaaS shell.
 */
type BrandMarkProps = {
  size?: number;
  className?: string;
  title?: string;
};

export default function BrandMark({ size = 32, className, title = "TSpace" }: BrandMarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label={title}
    >
      <rect width="32" height="32" rx="8" fill="var(--color-primary)" />
      <path
        d="M9 10.5h14v3.25H18.4V22h-4.8V13.75H9V10.5z"
        fill="var(--color-text-inverse, #fff)"
      />
    </svg>
  );
}
