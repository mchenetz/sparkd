import { ExternalLink } from "lucide-react";

import { useHFModel } from "../hooks/useHF";
import { Card, Pill } from "./Card";

export default function HFModelDetail({ id }: { id: string }) {
  const q = useHFModel(id);
  return (
    <Card>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 12,
          marginBottom: 10,
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
            selected model
          </div>
          <code style={{ fontSize: 14, fontWeight: 500 }}>{id}</code>
        </div>
        <a
          href={`https://huggingface.co/${id}`}
          target="_blank"
          rel="noreferrer"
          style={{ borderBottom: "none" }}
          title="open on huggingface.co"
        >
          <button className="ghost">
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <ExternalLink size={13} /> hf
            </span>
          </button>
        </a>
      </div>

      {q.isLoading ? (
        <div style={{ color: "var(--fg-muted)", fontSize: 12 }}>fetching facts…</div>
      ) : q.data ? (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "auto 1fr",
            gap: "6px 14px",
            fontFamily: "var(--font-mono)",
            fontSize: 12,
          }}
        >
          <span style={{ color: "var(--fg-muted)" }}>architecture</span>
          <span>{q.data.architecture || "—"}</span>
          <span style={{ color: "var(--fg-muted)" }}>parameters</span>
          <span>{q.data.parameters_b > 0 ? `${q.data.parameters_b} B` : "—"}</span>
          <span style={{ color: "var(--fg-muted)" }}>context</span>
          <span>{q.data.context_length ? q.data.context_length.toLocaleString() : "—"}</span>
          <span style={{ color: "var(--fg-muted)" }}>dtypes</span>
          <span>
            {q.data.supported_dtypes.length > 0 ? (
              q.data.supported_dtypes.map((d) => (
                <span key={d} style={{ marginRight: 6 }}>
                  <Pill tone="info">{d}</Pill>
                </span>
              ))
            ) : (
              "—"
            )}
          </span>
          <span style={{ color: "var(--fg-muted)" }}>license</span>
          <span>{q.data.license || "—"}</span>
          <span style={{ color: "var(--fg-muted)" }}>pipeline</span>
          <span>{q.data.pipeline_tag || "—"}</span>
        </div>
      ) : (
        <div style={{ color: "var(--signal-danger)" }}>failed to load model facts</div>
      )}
    </Card>
  );
}
