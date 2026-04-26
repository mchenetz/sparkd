import { ReactNode } from "react";

export type Tab = { id: string; label: ReactNode };

export default function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: Tab[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 4,
        borderBottom: "1px solid var(--border-subtle)",
        marginBottom: 20,
      }}
    >
      {tabs.map((t) => (
        <button
          key={t.id}
          className="ghost"
          onClick={() => onChange(t.id)}
          style={{
            padding: "10px 16px",
            borderRadius: 0,
            borderBottom:
              active === t.id
                ? "2px solid var(--fg-primary)"
                : "2px solid transparent",
            color: active === t.id ? "var(--fg-primary)" : "var(--fg-muted)",
            fontSize: 13,
            letterSpacing: "0.02em",
            transition: "all 140ms var(--ease-out)",
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
