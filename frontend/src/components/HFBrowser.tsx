import { Heart, Lock, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { HFModelSummary, useHFSearch } from "../hooks/useHF";
import { Card, EmptyState, Pill } from "./Card";

const PIPELINE_TAGS: { id: string; label: string }[] = [
  { id: "", label: "any task" },
  { id: "text-generation", label: "text-generation" },
  { id: "text2text-generation", label: "text2text-generation" },
  { id: "image-text-to-text", label: "image-text-to-text (vlm)" },
  { id: "automatic-speech-recognition", label: "asr" },
  { id: "feature-extraction", label: "feature-extraction" },
  { id: "fill-mask", label: "fill-mask" },
  { id: "image-classification", label: "image-classification" },
  { id: "image-to-text", label: "image-to-text" },
  { id: "text-to-image", label: "text-to-image" },
  { id: "translation", label: "translation" },
  { id: "summarization", label: "summarization" },
];

const LIBRARIES: { id: string; label: string }[] = [
  { id: "", label: "any library" },
  { id: "transformers", label: "transformers" },
  { id: "diffusers", label: "diffusers" },
  { id: "vllm", label: "vllm" },
  { id: "gguf", label: "gguf" },
  { id: "mlx", label: "mlx" },
];

const SORTS: { id: string; label: string }[] = [
  { id: "trending_score", label: "trending" },
  { id: "downloads", label: "downloads" },
  { id: "likes", label: "likes" },
  { id: "lastModified", label: "recently updated" },
  { id: "createdAt", label: "newest" },
];

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const ms = Date.now() - d.getTime();
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d ago`;
  const mo = Math.floor(day / 30);
  if (mo < 12) return `${mo}mo ago`;
  return `${Math.floor(mo / 12)}y ago`;
}

export default function HFBrowser({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [pipeline, setPipeline] = useState("text-generation");
  const [library, setLibrary] = useState("");
  const [sort, setSort] = useState("trending_score");
  const [debounced, setDebounced] = useState(query);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 300);
    return () => clearTimeout(t);
  }, [query]);

  const search = useHFSearch({
    q: debounced || undefined,
    pipeline_tag: pipeline || undefined,
    library: library || undefined,
    sort,
    limit: 30,
  });

  const results = search.data?.results ?? [];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 16 }}>
      <FilterRail
        pipeline={pipeline}
        setPipeline={setPipeline}
        library={library}
        setLibrary={setLibrary}
        sort={sort}
        setSort={setSort}
      />
      <div style={{ display: "grid", gap: 12, minWidth: 0 }}>
        <Card pad={12}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Search size={14} style={{ color: "var(--fg-muted)" }} />
            <input
              className="mono"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="search models on huggingface.co (name, author, tag…)"
              style={{ flex: 1, border: "none", background: "transparent" }}
            />
            {search.isFetching && (
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--fg-faint)",
                }}
              >
                searching…
              </span>
            )}
          </div>
        </Card>

        {results.length === 0 && !search.isLoading ? (
          <EmptyState title="No models found" hint="Adjust the filters or query." />
        ) : (
          <div
            style={{
              display: "grid",
              gap: 8,
              maxHeight: 540,
              overflowY: "auto",
              paddingRight: 4,
            }}
          >
            {results.map((m) => (
              <ModelRow
                key={m.id}
                m={m}
                selected={m.id === selected}
                onSelect={() => onSelect(m.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function FilterRail({
  pipeline,
  setPipeline,
  library,
  setLibrary,
  sort,
  setSort,
}: {
  pipeline: string;
  setPipeline: (v: string) => void;
  library: string;
  setLibrary: (v: string) => void;
  sort: string;
  setSort: (v: string) => void;
}) {
  return (
    <Card pad={14}>
      <RailGroup label="task">
        {PIPELINE_TAGS.map((t) => (
          <RailOption
            key={t.id}
            active={pipeline === t.id}
            onClick={() => setPipeline(t.id)}
          >
            {t.label}
          </RailOption>
        ))}
      </RailGroup>
      <div style={{ height: 14 }} />
      <RailGroup label="library">
        {LIBRARIES.map((t) => (
          <RailOption
            key={t.id}
            active={library === t.id}
            onClick={() => setLibrary(t.id)}
          >
            {t.label}
          </RailOption>
        ))}
      </RailGroup>
      <div style={{ height: 14 }} />
      <RailGroup label="sort">
        {SORTS.map((s) => (
          <RailOption
            key={s.id}
            active={sort === s.id}
            onClick={() => setSort(s.id)}
          >
            {s.label}
          </RailOption>
        ))}
      </RailGroup>
    </Card>
  );
}

function RailGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 10,
          color: "var(--fg-muted)",
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div style={{ display: "grid", gap: 2 }}>{children}</div>
    </div>
  );
}

function RailOption({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      className="ghost"
      onClick={onClick}
      style={{
        textAlign: "left",
        padding: "5px 8px",
        fontSize: 12,
        background: active ? "var(--bg-elev-3)" : "transparent",
        color: active ? "var(--fg-primary)" : "var(--fg-secondary)",
        borderLeft: active
          ? "2px solid var(--accent-ai)"
          : "2px solid transparent",
        borderRadius: 0,
      }}
    >
      {children}
    </button>
  );
}

function ModelRow({
  m,
  selected,
  onSelect,
}: {
  m: HFModelSummary;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      style={{
        textAlign: "left",
        background: selected ? "rgba(255,119,51,0.06)" : "var(--bg-elev-1)",
        border: `1px solid ${selected ? "rgba(255,119,51,0.4)" : "var(--border-subtle)"}`,
        borderRadius: "var(--radius-sm)",
        padding: "12px 14px",
        cursor: "pointer",
        transition: "all 140ms var(--ease-out)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 4,
          flexWrap: "wrap",
        }}
      >
        <code
          style={{
            fontSize: 13,
            fontWeight: 500,
            color: "var(--fg-primary)",
          }}
        >
          {m.id}
        </code>
        {selected && <Pill tone="ai">selected</Pill>}
        {m.gated && (
          <span
            title="gated repo"
            style={{ color: "var(--signal-warn)", display: "inline-flex", alignItems: "center" }}
          >
            <Lock size={11} />
          </span>
        )}
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--fg-muted)",
          flexWrap: "wrap",
        }}
      >
        <span>↓ {formatNumber(m.downloads)}</span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
          <Heart size={10} /> {formatNumber(m.likes)}
        </span>
        <span>{relativeTime(m.last_modified)}</span>
        {m.pipeline_tag && <Pill tone="info">{m.pipeline_tag}</Pill>}
        {m.library_name && (
          <span style={{ color: "var(--fg-faint)" }}>{m.library_name}</span>
        )}
      </div>
    </button>
  );
}
