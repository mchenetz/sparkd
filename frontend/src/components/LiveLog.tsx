import { useEffect, useRef, useState } from "react";

import { openWS } from "../api/client";

export default function LiveLog({ launchId }: { launchId: string }) {
  const [lines, setLines] = useState<{ channel: string; line: string }[]>([]);
  const [connected, setConnected] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const ws = openWS(`/ws/launches/${launchId}`);
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (ev) =>
      setLines((l) => [...l, JSON.parse(ev.data)].slice(-1000));
    return () => ws.close();
  }, [launchId]);
  useEffect(() => {
    ref.current?.scrollTo(0, ref.current.scrollHeight);
  }, [lines]);
  return (
    <div
      style={{
        marginTop: 12,
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-sm)",
        background: "var(--bg-overlay)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "6px 12px",
          background: "var(--bg-elev-2)",
          borderBottom: "1px solid var(--border-subtle)",
          fontFamily: "var(--font-mono)",
          fontSize: 10.5,
          color: "var(--fg-muted)",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
        }}
      >
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: 999,
            background: connected ? "var(--signal-healthy)" : "var(--fg-faint)",
            animation: connected
              ? "pulse-dot 2s var(--ease-in-out) infinite"
              : "none",
          }}
        />
        <span>{connected ? "tail -f" : "disconnected"}</span>
        <span style={{ color: "var(--fg-faint)" }}>·</span>
        <span style={{ color: "var(--fg-faint)" }}>
          {lines.length} line{lines.length === 1 ? "" : "s"}
        </span>
      </div>
      <div
        ref={ref}
        style={{
          height: 240,
          overflow: "auto",
          padding: "10px 14px",
          fontFamily: "var(--font-mono)",
          fontSize: 12,
          lineHeight: 1.55,
        }}
      >
        {lines.length === 0 ? (
          <div style={{ color: "var(--fg-faint)", fontStyle: "italic" }}>
            waiting for output…
          </div>
        ) : (
          lines.map((l, i) => (
            <div
              key={i}
              style={{
                color:
                  l.channel === "stderr"
                    ? "var(--signal-warn)"
                    : l.channel === "error"
                    ? "var(--signal-danger)"
                    : "var(--fg-secondary)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              <span
                style={{
                  display: "inline-block",
                  width: 32,
                  color: "var(--fg-faint)",
                  userSelect: "none",
                }}
              >
                {(i + 1).toString().padStart(3, " ")}
              </span>
              {l.line.replace(/\n$/, "")}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
