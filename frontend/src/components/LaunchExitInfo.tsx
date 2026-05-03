import { ChevronRight, ChevronDown, AlertCircle } from "lucide-react";
import { useState } from "react";

import type { ExitInfo } from "../hooks/useLaunches";

/**
 * Shows the inline "why did this die" line on a launch row that's reached
 * a terminal state. Reason is the one-line distillation extracted by the
 * backend; details expands to the full log tail captured at the
 * transition. Surfaced by the reconciler — the user shouldn't have to ssh
 * in to find out why a launch failed.
 */
export default function LaunchExitInfo({ exitInfo }: { exitInfo: ExitInfo | null }) {
  const [open, setOpen] = useState(false);

  if (!exitInfo || (!exitInfo.reason && !exitInfo.tail?.length)) return null;

  return (
    <div
      style={{
        marginTop: 10,
        paddingTop: 10,
        borderTop: "1px dashed var(--border-subtle)",
        display: "grid",
        gap: 8,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 8,
          fontSize: 12,
          color: "var(--signal-danger)",
        }}
      >
        <AlertCircle
          size={13}
          style={{ flexShrink: 0, marginTop: 1 }}
        />
        <span
          style={{
            fontFamily: "var(--font-mono)",
            wordBreak: "break-word",
            flex: 1,
            color: "var(--fg-secondary)",
          }}
        >
          {exitInfo.reason || "(no error message captured)"}
        </span>
        {exitInfo.tail && exitInfo.tail.length > 0 && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            style={{
              background: "transparent",
              border: "none",
              padding: 0,
              cursor: "pointer",
              color: "var(--fg-muted)",
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              display: "inline-flex",
              alignItems: "center",
              gap: 2,
            }}
          >
            {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            {open ? "hide" : "tail"}
          </button>
        )}
      </div>
      {open && (
        <pre
          style={{
            margin: 0,
            padding: "10px 12px",
            background: "var(--bg-base)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-sm)",
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--fg-secondary)",
            maxHeight: 280,
            overflow: "auto",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {exitInfo.tail.join("\n")}
        </pre>
      )}
    </div>
  );
}
