/**
 * Official Algenta logo — inline SVG for crisp rendering at any size.
 * Two-path mark: green (bottom-left) + purple (top-right).
 */
export function Logo({
  width = 32,
  height = 21,
  className = "",
}: {
  width?: number;
  height?: number;
  className?: string;
}) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 32 21"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Algenta"
    >
      <path
        d="M0 21.0099C6.78967 21.0099 10.6973 15.7585 14.8567 10.5049H0V21.0099Z"
        fill="#00FF80"
      />
      <path
        d="M31.2359 0C23.4322 0 19.0186 5.25135 14.8569 10.505H20.7538V21.01H31.2588L31.2336 0H31.2359Z"
        fill="#6B42FC"
      />
    </svg>
  );
}

/** Logo + wordmark lockup */
export function LogoLockup({
  logoSize = 24,
  fontSize = 16,
  fontWeight = 600,
  color = "#333333",
  gap = 10,
}: {
  logoSize?: number;
  fontSize?: number;
  fontWeight?: number;
  color?: string;
  gap?: number;
}) {
  const logoHeight = Math.round((logoSize * 21) / 32); // maintain 32:21 aspect ratio
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: `${gap}px`,
      }}
    >
      <Logo width={logoSize} height={logoHeight} />
      <span
        style={{
          fontFamily: "'Articulat CF', 'Inter', system-ui, sans-serif",
          fontWeight,
          fontSize: `${fontSize}px`,
          lineHeight: 1,
          color,
          letterSpacing: "0.01em",
        }}
      >
        Algenta
      </span>
    </div>
  );
}
