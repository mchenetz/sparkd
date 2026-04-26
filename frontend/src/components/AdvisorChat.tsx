export default function AdvisorChat({
  text,
  loading,
}: {
  text: string;
  loading: boolean;
}) {
  return (
    <pre
      style={{
        background: "#111",
        color: "#eee",
        padding: 12,
        minHeight: 120,
        whiteSpace: "pre-wrap",
        fontFamily: "ui-monospace, monospace",
      }}
    >
      {text}
      {loading && <span style={{ opacity: 0.6 }}>▌</span>}
    </pre>
  );
}
