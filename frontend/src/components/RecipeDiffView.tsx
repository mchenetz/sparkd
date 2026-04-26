import { Check, X } from "lucide-react";

import { RecipeDraft } from "../hooks/useAdvisor";
import { Recipe } from "../hooks/useRecipes";
import { Card, Pill } from "./Card";

type Change<T> = { before: T; after: T };
type DictDiff = {
  added: Record<string, string>;
  removed: Record<string, string>;
  changed: Record<string, Change<string>>;
};

function diffDict(
  a: Record<string, string>,
  b: Record<string, string>,
): DictDiff {
  const added: Record<string, string> = {};
  const removed: Record<string, string> = {};
  const changed: Record<string, Change<string>> = {};
  for (const k of Object.keys(b)) {
    if (!(k in a)) added[k] = b[k];
    else if (a[k] !== b[k]) changed[k] = { before: a[k], after: b[k] };
  }
  for (const k of Object.keys(a)) {
    if (!(k in b)) removed[k] = a[k];
  }
  return { added, removed, changed };
}

function diffList(a: string[], b: string[]) {
  const sa = new Set(a);
  const sb = new Set(b);
  return {
    added: b.filter((x) => !sa.has(x)),
    removed: a.filter((x) => !sb.has(x)),
  };
}

function isEmptyDictDiff(d: DictDiff) {
  return (
    Object.keys(d.added).length === 0 &&
    Object.keys(d.removed).length === 0 &&
    Object.keys(d.changed).length === 0
  );
}

export default function RecipeDiffView({
  base,
  proposed,
  onApply,
  onDiscard,
}: {
  base: Recipe;
  proposed: RecipeDraft;
  onApply: () => void;
  onDiscard: () => void;
}) {
  const modelChange =
    base.model !== proposed.model
      ? { before: base.model, after: proposed.model }
      : null;
  const descChange =
    (base.description ?? "") !== (proposed.description ?? "")
      ? {
          before: base.description ?? "",
          after: proposed.description ?? "",
        }
      : null;
  const argsDiff = diffDict(base.args ?? {}, proposed.args ?? {});
  const envDiff = diffDict(base.env ?? {}, proposed.env ?? {});
  const noChanges =
    !modelChange && !descChange && isEmptyDictDiff(argsDiff) && isEmptyDictDiff(envDiff);
  return (
    <Card ai>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginBottom: 16,
          gap: 12,
        }}
      >
        <div>
          <Pill tone="ai">proposed change</Pill>
          <h3 style={{ marginTop: 6 }}>Diff</h3>
          <p style={{ color: "var(--fg-muted)", fontSize: 13, marginTop: 4 }}>
            Apply replaces matching fields in the form. Discard drops the
            suggestion. Save the form afterward to persist changes.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="ghost" onClick={onDiscard}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <X size={13} /> discard
            </span>
          </button>
          <button className="ai" onClick={onApply} disabled={noChanges}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <Check size={13} /> apply to form
            </span>
          </button>
        </div>
      </div>

      {noChanges ? (
        <div
          style={{
            padding: "16px 18px",
            background: "var(--bg-overlay)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-sm)",
            color: "var(--fg-muted)",
            fontStyle: "italic",
          }}
        >
          No changes — the proposal matches the current form values.
        </div>
      ) : (
        <div style={{ display: "grid", gap: 14 }}>
          {modelChange && (
            <Section label="model">
              <ChangedRow before={modelChange.before} after={modelChange.after} />
            </Section>
          )}
          {descChange && (
            <Section label="description">
              <ChangedRow before={descChange.before} after={descChange.after} />
            </Section>
          )}
          <DictSection label="args" diff={argsDiff} />
          <DictSection label="env" diff={envDiff} />
        </div>
      )}

      {proposed.rationale && (
        <div
          style={{
            marginTop: 18,
            padding: "12px 16px",
            borderLeft: "2px solid var(--accent-ai)",
            background: "rgba(255,119,51,0.05)",
            color: "var(--fg-secondary)",
            fontStyle: "italic",
            fontSize: 13,
          }}
        >
          {proposed.rationale}
        </div>
      )}
    </Card>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--fg-muted)",
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      {children}
    </div>
  );
}

function DictSection({ label, diff }: { label: string; diff: DictDiff }) {
  if (isEmptyDictDiff(diff)) return null;
  return (
    <Section label={label}>
      <div
        style={{
          background: "var(--bg-overlay)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-sm)",
          padding: "10px 14px",
          display: "grid",
          gap: 4,
        }}
      >
        {Object.entries(diff.added).map(([k, v]) => (
          <DiffLine key={`+${k}`} sigil="+" tone="add">
            <code>{k}</code>: <code>{v}</code>
          </DiffLine>
        ))}
        {Object.entries(diff.removed).map(([k, v]) => (
          <DiffLine key={`-${k}`} sigil="−" tone="remove">
            <code>{k}</code>: <code>{v}</code>
          </DiffLine>
        ))}
        {Object.entries(diff.changed).map(([k, c]) => (
          <DiffLine key={`~${k}`} sigil="~" tone="change">
            <code>{k}</code>: <code style={{ textDecoration: "line-through" }}>
              {c.before}
            </code>{" "}
            → <code>{c.after}</code>
          </DiffLine>
        ))}
      </div>
    </Section>
  );
}

function DiffLine({
  sigil,
  tone,
  children,
}: {
  sigil: string;
  tone: "add" | "remove" | "change";
  children: React.ReactNode;
}) {
  const colors: Record<typeof tone, string> = {
    add: "var(--signal-healthy)",
    remove: "var(--signal-danger)",
    change: "var(--signal-warn)",
  };
  return (
    <div
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: 12,
        display: "grid",
        gridTemplateColumns: "16px 1fr",
        gap: 6,
        color: "var(--fg-primary)",
      }}
    >
      <span style={{ color: colors[tone], fontWeight: 600 }}>{sigil}</span>
      <span>{children}</span>
    </div>
  );
}

function ChangedRow({ before, after }: { before: string; after: string }) {
  return (
    <div
      style={{
        background: "var(--bg-overlay)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-sm)",
        padding: "10px 14px",
        display: "grid",
        gap: 4,
        fontFamily: "var(--font-mono)",
        fontSize: 12,
      }}
    >
      <div style={{ color: "var(--signal-danger)" }}>− {before || "(empty)"}</div>
      <div style={{ color: "var(--signal-healthy)" }}>+ {after || "(empty)"}</div>
    </div>
  );
}
