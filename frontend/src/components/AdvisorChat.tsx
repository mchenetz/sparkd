export default function AdvisorChat({
  text,
  loading,
}: {
  text: string;
  loading: boolean;
}) {
  return (
    <div
      style={{
        position: "relative",
        background: "var(--bg-overlay)",
        border: "1px solid rgba(255,119,51,0.2)",
        borderRadius: "var(--radius-md)",
        overflow: "hidden",
        boxShadow: text || loading ? "var(--accent-ai-glow)" : "none",
        transition: "box-shadow 320ms var(--ease-out)",
      }}
    >
      <div
        style={{
          background:
            "linear-gradient(180deg, rgba(255,119,51,0.06) 0%, transparent 80%)",
          padding: "8px 14px",
          fontFamily: "var(--font-mono)",
          fontSize: 10.5,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: "var(--accent-ai)",
          borderBottom: "1px solid rgba(255,119,51,0.15)",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <span
          style={{
            width: 5,
            height: 5,
            borderRadius: 999,
            background: "var(--accent-ai)",
            animation: loading ? "pulse-dot 1.2s var(--ease-in-out) infinite" : "none",
          }}
        />
        advisor stream
        {loading && <span style={{ color: "var(--fg-faint)" }}>· thinking</span>}
      </div>
      <pre
        style={{
          margin: 0,
          padding: "16px 18px",
          minHeight: 140,
          fontFamily: "var(--font-mono)",
          fontSize: 12.5,
          lineHeight: 1.65,
          color: "var(--fg-primary)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          maxHeight: 360,
          overflow: "auto",
        }}
      >
        {text || (
          <span style={{ color: "var(--fg-faint)", fontStyle: "italic" }}>
            ready.
          </span>
        )}
        {loading && (
          <span
            style={{
              color: "var(--accent-ai)",
              animation: "blink-caret 0.9s steps(1) infinite",
            }}
          >
            ▌
          </span>
        )}
      </pre>
    </div>
  );
}
