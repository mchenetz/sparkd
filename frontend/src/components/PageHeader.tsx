import { ReactNode } from "react";

export default function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  ai,
}: {
  eyebrow?: string;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  ai?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "space-between",
        gap: 24,
        paddingBottom: 24,
        borderBottom: "1px solid var(--border-subtle)",
        marginBottom: 28,
      }}
    >
      <div>
        {eyebrow && (
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: ai ? "var(--accent-ai)" : "var(--fg-muted)",
              marginBottom: 8,
            }}
          >
            {eyebrow}
          </div>
        )}
        <h1>{title}</h1>
        {subtitle && (
          <div
            style={{
              marginTop: 8,
              color: "var(--fg-secondary)",
              fontSize: 14,
              maxWidth: 640,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
      {actions && (
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>{actions}</div>
      )}
    </div>
  );
}
