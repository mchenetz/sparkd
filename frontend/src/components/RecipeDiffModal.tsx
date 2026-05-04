import { ArrowRight, Minus, Plus, X } from "lucide-react";
import { useEffect } from "react";

import type { Recipe } from "../hooks/useRecipes";
import { Pill } from "./Card";

/**
 * Side-by-side diff of two recipes. Pure client-side — both Recipe
 * objects are already loaded by the parent page (useRecipes).
 *
 * Layout: header with both names + close, then four sections in
 * priority order: top-level fields (model/description/mods), args
 * diff (added/removed/changed grouped), env diff (same shape).
 * Sections collapse to "no differences" when both sides match.
 */
export default function RecipeDiffModal({
  a,
  b,
  onClose,
}: {
  a: Recipe;
  b: Recipe;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const argDiff = diffMap(a.args, b.args);
  const envDiff = diffMap(a.env, b.env);
  const topFields = topLevelDiff(a, b);

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--bg-elev-2)",
          border: "1px solid var(--border-strong)",
          borderRadius: "var(--radius-md)",
          width: "min(1100px, 95vw)",
          maxHeight: "90vh",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "14px 18px",
            borderBottom: "1px solid var(--border-subtle)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <code
              style={{
                fontSize: 14,
                fontWeight: 500,
                color: "var(--fg-primary)",
              }}
            >
              {a.name}
            </code>
            <ArrowRight size={14} style={{ color: "var(--fg-muted)" }} />
            <code
              style={{
                fontSize: 14,
                fontWeight: 500,
                color: "var(--fg-primary)",
              }}
            >
              {b.name}
            </code>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--fg-muted)",
              cursor: "pointer",
              padding: 4,
            }}
            aria-label="close"
          >
            <X size={18} />
          </button>
        </div>

        <div
          style={{
            flex: 1,
            overflow: "auto",
            padding: 18,
            display: "grid",
            gap: 22,
          }}
        >
          <Section title="recipe">
            {topFields.length === 0 ? (
              <Empty />
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <Row
                    cells={["field", a.name, b.name]}
                    isHeader
                  />
                </thead>
                <tbody>
                  {topFields.map(([field, av, bv]) => (
                    <Row
                      key={field}
                      cells={[field, av, bv]}
                      tone="changed"
                    />
                  ))}
                </tbody>
              </table>
            )}
          </Section>

          <Section title={`args (${argDiff.summary})`}>
            <DiffTable diff={argDiff} aLabel={a.name} bLabel={b.name} />
          </Section>

          <Section title={`env (${envDiff.summary})`}>
            <DiffTable diff={envDiff} aLabel={a.name} bLabel={b.name} />
          </Section>
        </div>
      </div>
    </div>
  );
}

// ---------- bits ----------

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h4
        style={{
          margin: 0,
          marginBottom: 10,
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: "var(--fg-muted)",
        }}
      >
        {title}
      </h4>
      {children}
    </div>
  );
}

function Empty() {
  return (
    <div
      style={{
        padding: "12px 14px",
        fontFamily: "var(--font-mono)",
        fontSize: 12,
        color: "var(--fg-faint)",
        background: "var(--bg-elev-1)",
        borderRadius: "var(--radius-sm)",
      }}
    >
      no differences
    </div>
  );
}

type DiffMap = {
  added: Array<[string, string]>;
  removed: Array<[string, string]>;
  changed: Array<[string, string, string]>;
  summary: string;
};

function diffMap(
  a: Record<string, string>,
  b: Record<string, string>,
): DiffMap {
  const added: Array<[string, string]> = [];
  const removed: Array<[string, string]> = [];
  const changed: Array<[string, string, string]> = [];
  for (const [k, v] of Object.entries(b)) {
    if (!(k in a)) added.push([k, v]);
    else if (a[k] !== v) changed.push([k, a[k], v]);
  }
  for (const [k, v] of Object.entries(a)) {
    if (!(k in b)) removed.push([k, v]);
  }
  added.sort((x, y) => x[0].localeCompare(y[0]));
  removed.sort((x, y) => x[0].localeCompare(y[0]));
  changed.sort((x, y) => x[0].localeCompare(y[0]));
  const total = added.length + removed.length + changed.length;
  const summary =
    total === 0
      ? "identical"
      : `${added.length} added, ${removed.length} removed, ${changed.length} changed`;
  return { added, removed, changed, summary };
}

function topLevelDiff(
  a: Recipe,
  b: Recipe,
): Array<[string, string, string]> {
  const out: Array<[string, string, string]> = [];
  if (a.model !== b.model) out.push(["model", a.model, b.model]);
  if ((a.description ?? "") !== (b.description ?? "")) {
    out.push(["description", a.description ?? "", b.description ?? ""]);
  }
  const aMods = [...a.mods].sort().join(", ");
  const bMods = [...b.mods].sort().join(", ");
  if (aMods !== bMods)
    out.push(["mods", aMods || "—", bMods || "—"]);
  return out;
}

function DiffTable({
  diff,
  aLabel,
  bLabel,
}: {
  diff: DiffMap;
  aLabel: string;
  bLabel: string;
}) {
  if (diff.summary === "identical") return <Empty />;
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <Row cells={["", aLabel, bLabel]} isHeader />
      </thead>
      <tbody>
        {diff.removed.map(([k, v]) => (
          <Row
            key={`r-${k}`}
            cells={[
              <span
                key="k"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <Minus size={11} style={{ color: "var(--signal-danger)" }} />
                <code>{k}</code>
              </span>,
              v,
              <span key="-" style={{ color: "var(--fg-faint)" }}>
                —
              </span>,
            ]}
            tone="removed"
          />
        ))}
        {diff.added.map(([k, v]) => (
          <Row
            key={`a-${k}`}
            cells={[
              <span
                key="k"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <Plus size={11} style={{ color: "var(--signal-healthy)" }} />
                <code>{k}</code>
              </span>,
              <span key="-" style={{ color: "var(--fg-faint)" }}>
                —
              </span>,
              v,
            ]}
            tone="added"
          />
        ))}
        {diff.changed.map(([k, av, bv]) => (
          <Row
            key={`c-${k}`}
            cells={[
              <span key="k">
                <code>{k}</code>{" "}
                <Pill tone="warn">changed</Pill>
              </span>,
              av,
              bv,
            ]}
            tone="changed"
          />
        ))}
      </tbody>
    </table>
  );
}

function Row({
  cells,
  isHeader = false,
  tone = "neutral",
}: {
  cells: Array<React.ReactNode>;
  isHeader?: boolean;
  tone?: "neutral" | "added" | "removed" | "changed";
}) {
  const cellBg =
    tone === "added"
      ? "rgba(77,255,166,0.04)"
      : tone === "removed"
        ? "rgba(255,89,97,0.04)"
        : tone === "changed"
          ? "rgba(255,181,71,0.04)"
          : "transparent";
  const Tag = isHeader ? "th" : "td";
  return (
    <tr style={{ background: cellBg }}>
      {cells.map((c, i) => (
        <Tag
          key={i}
          style={{
            padding: "8px 12px",
            fontSize: 12,
            fontFamily: i === 0 ? "var(--font-mono)" : "var(--font-mono)",
            color: isHeader ? "var(--fg-muted)" : "var(--fg-secondary)",
            verticalAlign: "top",
            textAlign: "left",
            borderBottom: "1px solid var(--border-subtle)",
            wordBreak: "break-word",
            width: i === 0 ? "26%" : "37%",
            letterSpacing: isHeader ? "0.06em" : undefined,
            textTransform: isHeader ? "uppercase" : undefined,
            fontWeight: isHeader ? 500 : 400,
          }}
        >
          {c}
        </Tag>
      ))}
    </tr>
  );
}
