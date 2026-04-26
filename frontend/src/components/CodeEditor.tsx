import { useEffect, useRef } from "react";

export default function CodeEditor({
  value,
  onChange,
  height = 480,
  readOnly = false,
}: {
  value: string;
  onChange?: (next: string) => void;
  height?: number;
  readOnly?: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // line-number gutter via background-image trick is complex; keep textarea
    // as-is but allow Tab to insert spaces.
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Tab") {
        e.preventDefault();
        const start = el.selectionStart;
        const end = el.selectionEnd;
        const next = el.value.slice(0, start) + "  " + el.value.slice(end);
        el.value = next;
        el.selectionStart = el.selectionEnd = start + 2;
        onChange?.(next);
      }
    };
    el.addEventListener("keydown", handler);
    return () => el.removeEventListener("keydown", handler);
  }, [onChange]);
  return (
    <div
      style={{
        position: "relative",
        background: "var(--bg-overlay)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-sm)",
        overflow: "hidden",
      }}
    >
      <textarea
        ref={ref}
        value={value}
        readOnly={readOnly}
        onChange={(e) => onChange?.(e.target.value)}
        spellCheck={false}
        style={{
          width: "100%",
          height,
          padding: "14px 16px",
          background: "transparent",
          border: "none",
          color: "var(--fg-primary)",
          fontFamily: "var(--font-mono)",
          fontSize: 12.5,
          lineHeight: 1.6,
          resize: "vertical",
          outline: "none",
        }}
      />
    </div>
  );
}
