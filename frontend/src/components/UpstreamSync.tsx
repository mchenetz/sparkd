import { CloudDownload } from "lucide-react";
import { useState } from "react";
import { UseMutationResult } from "@tanstack/react-query";

import { Card } from "./Card";
import { UpstreamSyncResult } from "../hooks/useUpstream";

const DEFAULT_REPO = "eugr/spark-vllm-docker";
const DEFAULT_BRANCH = "main";

type SyncMutation = UseMutationResult<
  UpstreamSyncResult,
  unknown,
  { repo?: string; branch?: string; force?: boolean }
>;

function Summary({ result }: { result: UpstreamSyncResult }) {
  const total =
    result.imported.length + result.skipped.length + result.errors.length;
  if (total === 0) return null;
  return (
    <div
      style={{
        marginTop: 14,
        padding: "12px 14px",
        background: "var(--bg-overlay)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-sm)",
        fontFamily: "var(--font-mono)",
        fontSize: 12,
        display: "grid",
        gap: 6,
      }}
    >
      <div style={{ display: "flex", gap: 14, color: "var(--fg-muted)" }}>
        <span>
          <span style={{ color: "var(--signal-healthy)" }}>
            {result.imported.length}
          </span>{" "}
          imported
        </span>
        <span>
          <span style={{ color: "var(--fg-secondary)" }}>{result.skipped.length}</span>{" "}
          skipped
        </span>
        <span>
          <span style={{ color: "var(--signal-danger)" }}>{result.errors.length}</span>{" "}
          errors
        </span>
        <span style={{ flex: 1 }} />
        <span style={{ color: "var(--fg-faint)" }}>
          {result.repo}@{result.branch}
        </span>
      </div>
      {result.imported.length > 0 && (
        <details>
          <summary style={{ cursor: "pointer", color: "var(--signal-healthy)" }}>
            imported
          </summary>
          <div style={{ paddingLeft: 14, color: "var(--fg-secondary)" }}>
            {result.imported.map((n) => (
              <div key={n}>+ {n}</div>
            ))}
          </div>
        </details>
      )}
      {result.skipped.length > 0 && (
        <details>
          <summary style={{ cursor: "pointer", color: "var(--fg-secondary)" }}>
            skipped (use force to overwrite)
          </summary>
          <div style={{ paddingLeft: 14, color: "var(--fg-muted)" }}>
            {result.skipped.map((n) => (
              <div key={n}>= {n}</div>
            ))}
          </div>
        </details>
      )}
      {result.errors.length > 0 && (
        <details open>
          <summary style={{ cursor: "pointer", color: "var(--signal-danger)" }}>
            errors
          </summary>
          <div style={{ paddingLeft: 14, color: "var(--signal-danger)" }}>
            {result.errors.map((e) => (
              <div key={e.name}>
                ! {e.name}: {e.message}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

export default function UpstreamSync({
  label,
  sync,
}: {
  label: string;
  sync: SyncMutation;
}) {
  const [repo, setRepo] = useState(DEFAULT_REPO);
  const [branch, setBranch] = useState(DEFAULT_BRANCH);
  const [force, setForce] = useState(false);
  const [open, setOpen] = useState(false);
  return (
    <Card>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--fg-muted)",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              marginBottom: 4,
            }}
          >
            upstream sync · {label}
          </div>
          <div style={{ fontSize: 13, color: "var(--fg-secondary)" }}>
            Pull {label} from{" "}
            <code style={{ color: "var(--fg-primary)" }}>{repo}</code>
            <span style={{ color: "var(--fg-faint)" }}>@</span>
            <code style={{ color: "var(--fg-primary)" }}>{branch}</code>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="ghost" onClick={() => setOpen((o) => !o)}>
            {open ? "hide" : "configure"}
          </button>
          <button
            className="primary"
            disabled={sync.isPending}
            onClick={() => sync.mutate({ repo, branch, force })}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <CloudDownload size={14} />
              {sync.isPending ? "syncing…" : "sync"}
            </span>
          </button>
        </div>
      </div>
      {open && (
        <div
          style={{
            marginTop: 14,
            display: "grid",
            gridTemplateColumns: "2fr 1fr auto",
            gap: 8,
            alignItems: "center",
          }}
        >
          <input
            className="mono"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            placeholder="owner/repo"
          />
          <input
            className="mono"
            value={branch}
            onChange={(e) => setBranch(e.target.value)}
            placeholder="branch"
          />
          <label
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
              color: "var(--fg-secondary)",
            }}
          >
            <input
              type="checkbox"
              checked={force}
              onChange={(e) => setForce(e.target.checked)}
            />
            overwrite existing
          </label>
        </div>
      )}
      {sync.data && <Summary result={sync.data} />}
      {sync.error ? (
        <div
          style={{
            marginTop: 12,
            padding: "10px 14px",
            background: "rgba(255,89,97,0.08)",
            border: "1px solid rgba(255,89,97,0.3)",
            borderRadius: "var(--radius-sm)",
            color: "var(--signal-danger)",
            fontFamily: "var(--font-mono)",
            fontSize: 12,
          }}
        >
          {sync.error instanceof Error ? sync.error.message : String(sync.error)}
        </div>
      ) : null}
    </Card>
  );
}
