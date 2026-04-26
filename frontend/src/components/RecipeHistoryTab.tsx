import { Eye, RotateCcw, X } from "lucide-react";
import { useState } from "react";

import { Card, EmptyState, Pill } from "./Card";
import CodeEditor from "./CodeEditor";
import {
  RecipeVersionSummary,
  useRecipeVersion,
  useRecipeVersions,
  useRevertRecipe,
} from "../hooks/useRecipeVersions";

const SOURCE_TONE: Record<string, "neutral" | "info" | "warn" | "ai" | "healthy"> = {
  manual: "info",
  raw: "info",
  sync: "neutral",
  ai: "ai",
  revert: "warn",
  created: "healthy",
};

export default function RecipeHistoryTab({ name }: { name: string }) {
  const list = useRecipeVersions(name);
  const revert = useRevertRecipe();
  const [viewing, setViewing] = useState<number | null>(null);
  const versions = list.data?.versions ?? [];

  if (list.isLoading) return <Card>loading…</Card>;
  if (versions.length === 0) {
    return <EmptyState title="No history yet" hint="Saves will appear here." />;
  }

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <Card pad={0}>
        <table>
          <thead>
            <tr>
              <th style={{ width: 60 }}>v</th>
              <th>when</th>
              <th>source</th>
              <th>note</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {versions.map((v, idx) => (
              <Row
                key={v.id}
                v={v}
                isLatest={idx === 0}
                onView={() => setViewing(v.version)}
                onRevert={async () => {
                  if (!confirm(`Revert ${name} to v${v.version}?`)) return;
                  await revert.mutateAsync({ name, version: v.version });
                  setViewing(null);
                }}
                disabled={revert.isPending}
              />
            ))}
          </tbody>
        </table>
      </Card>
      {viewing !== null && (
        <VersionViewer
          name={name}
          version={viewing}
          onClose={() => setViewing(null)}
        />
      )}
    </div>
  );
}

function Row({
  v,
  isLatest,
  onView,
  onRevert,
  disabled,
}: {
  v: RecipeVersionSummary;
  isLatest: boolean;
  onView: () => void;
  onRevert: () => void;
  disabled: boolean;
}) {
  return (
    <tr>
      <td>
        <code style={{ fontWeight: 500 }}>v{v.version}</code>
      </td>
      <td>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            color: "var(--fg-secondary)",
          }}
        >
          {new Date(v.created_at).toLocaleString()}
        </span>
      </td>
      <td>
        <Pill tone={SOURCE_TONE[v.source] ?? "neutral"}>{v.source}</Pill>
        {isLatest && (
          <span style={{ marginLeft: 8 }}>
            <Pill tone="healthy">current</Pill>
          </span>
        )}
      </td>
      <td>
        <span style={{ color: "var(--fg-muted)", fontSize: 12 }}>
          {v.note || "—"}
        </span>
      </td>
      <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
        <button className="ghost" onClick={onView}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <Eye size={13} /> view
          </span>
        </button>
        {!isLatest && (
          <button className="ghost" disabled={disabled} onClick={onRevert}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <RotateCcw size={13} /> revert
            </span>
          </button>
        )}
      </td>
    </tr>
  );
}

function VersionViewer({
  name,
  version,
  onClose,
}: {
  name: string;
  version: number;
  onClose: () => void;
}) {
  const q = useRecipeVersion(name, version);
  return (
    <Card>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 10,
        }}
      >
        <div>
          <Pill tone="info">v{version}</Pill>
          {q.data?.note && (
            <span
              style={{
                marginLeft: 10,
                color: "var(--fg-muted)",
                fontSize: 12,
              }}
            >
              {q.data.note}
            </span>
          )}
        </div>
        <button className="ghost" onClick={onClose}>
          <X size={13} />
        </button>
      </div>
      {q.isLoading ? (
        <div style={{ color: "var(--fg-muted)" }}>loading…</div>
      ) : q.error ? (
        <div style={{ color: "var(--signal-danger)" }}>{String(q.error)}</div>
      ) : (
        <CodeEditor value={q.data?.yaml_text ?? ""} readOnly height={420} />
      )}
    </Card>
  );
}
