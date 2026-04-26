import { CSSProperties, ReactNode } from "react";

export function Card({
  children,
  pad = 20,
  style,
  ai,
}: {
  children: ReactNode;
  pad?: number;
  style?: CSSProperties;
  ai?: boolean;
}) {
  return (
    <div
      style={{
        background: "var(--bg-elev-1)",
        border: `1px solid ${ai ? "rgba(255,119,51,0.25)" : "var(--border-subtle)"}`,
        borderRadius: "var(--radius-md)",
        padding: pad,
        boxShadow: "var(--shadow-card)",
        position: "relative",
        ...style,
      }}
    >
      {ai && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: "var(--radius-md)",
            background:
              "radial-gradient(800px circle at 0% 0%, rgba(255,119,51,0.06), transparent 40%)",
            pointerEvents: "none",
          }}
        />
      )}
      <div style={{ position: "relative" }}>{children}</div>
    </div>
  );
}

export function CardHeader({
  title,
  meta,
  right,
}: {
  title: ReactNode;
  meta?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "baseline",
        justifyContent: "space-between",
        gap: 16,
        marginBottom: 14,
      }}
    >
      <div>
        <div style={{ fontSize: 14, fontWeight: 500 }}>{title}</div>
        {meta && (
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--fg-muted)",
              marginTop: 2,
            }}
          >
            {meta}
          </div>
        )}
      </div>
      {right}
    </div>
  );
}

export function Pill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "healthy" | "warn" | "danger" | "ai" | "info";
}) {
  const colors: Record<typeof tone, { bg: string; fg: string }> = {
    neutral: { bg: "var(--bg-elev-3)", fg: "var(--fg-secondary)" },
    healthy: { bg: "rgba(77,255,166,0.08)", fg: "var(--signal-healthy)" },
    warn: { bg: "rgba(255,181,71,0.1)", fg: "var(--signal-warn)" },
    danger: { bg: "rgba(255,89,97,0.1)", fg: "var(--signal-danger)" },
    info: { bg: "rgba(108,182,255,0.08)", fg: "var(--signal-info)" },
    ai: { bg: "rgba(255,119,51,0.1)", fg: "var(--accent-ai)" },
  };
  const { bg, fg } = colors[tone];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "2px 8px",
        borderRadius: 999,
        background: bg,
        color: fg,
        fontFamily: "var(--font-mono)",
        fontSize: 10.5,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        fontWeight: 500,
      }}
    >
      {children}
    </span>
  );
}

export function EmptyState({
  title,
  hint,
  icon,
}: {
  title: string;
  hint?: string;
  icon?: ReactNode;
}) {
  return (
    <div
      style={{
        padding: "56px 24px",
        textAlign: "center",
        color: "var(--fg-muted)",
        border: "1px dashed var(--border-subtle)",
        borderRadius: "var(--radius-md)",
        background:
          "repeating-linear-gradient(45deg, transparent 0 6px, rgba(255,255,255,0.012) 6px 7px)",
      }}
    >
      {icon && <div style={{ marginBottom: 12, opacity: 0.6 }}>{icon}</div>}
      <div
        style={{
          fontFamily: "var(--font-display)",
          fontSize: 22,
          color: "var(--fg-secondary)",
          fontStyle: "italic",
        }}
      >
        {title}
      </div>
      {hint && <div style={{ marginTop: 6, fontSize: 13 }}>{hint}</div>}
    </div>
  );
}
