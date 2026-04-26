import { X } from "lucide-react";
import { useEffect } from "react";

import { useLaunchInspect } from "../hooks/useLaunches";

export default function InspectModal({
  launchId,
  onClose,
}: {
  launchId: string;
  onClose: () => void;
}) {
  const q = useLaunchInspect(launchId);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
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
          width: "min(900px, 92vw)",
          maxHeight: "84vh",
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
            padding: "12px 18px",
            borderBottom: "1px solid var(--border-subtle)",
          }}
        >
          <div>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--fg-muted)",
                letterSpacing: "0.18em",
                textTransform: "uppercase",
              }}
            >
              docker inspect
            </div>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 13,
                color: "var(--fg-secondary)",
                marginTop: 2,
              }}
            >
              {q.data?.container_id ?? launchId}
            </div>
          </div>
          <button className="ghost" onClick={onClose}>
            <X size={14} />
          </button>
        </div>
        <div
          style={{
            padding: "14px 18px",
            overflow: "auto",
            background: "var(--bg-overlay)",
            flex: 1,
          }}
        >
          {q.isLoading && <div style={{ color: "var(--fg-muted)" }}>loading…</div>}
          {q.error && (
            <div style={{ color: "var(--signal-danger)" }}>{String(q.error)}</div>
          )}
          {q.data?.error && (
            <div style={{ color: "var(--signal-warn)" }}>{q.data.error}</div>
          )}
          {q.data?.inspect && (
            <pre
              style={{
                margin: 0,
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                color: "var(--fg-primary)",
                lineHeight: 1.55,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {JSON.stringify(q.data.inspect, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
