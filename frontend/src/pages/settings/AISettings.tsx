import { Check, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Card, Pill } from "../../components/Card";
import {
  ProviderDef,
  useAdvisorConfig,
  useProviders,
  usePutAdvisorConfig,
} from "../../hooks/useAdvisorConfig";

export default function AISettings() {
  const providers = useProviders();
  const config = useAdvisorConfig();
  const put = usePutAdvisorConfig();

  const [providerId, setProviderId] = useState<string>("");
  const [model, setModel] = useState("");
  const [modelMode, setModelMode] = useState<"select" | "custom">("select");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [makeActive, setMakeActive] = useState(true);

  // Initialize from server state when it arrives.
  useEffect(() => {
    if (!providers.data || !config.data) return;
    if (!providerId) {
      setProviderId(config.data.active_provider);
    }
  }, [providers.data, config.data, providerId]);

  const provider: ProviderDef | undefined = useMemo(
    () => providers.data?.providers.find((p) => p.id === providerId),
    [providers.data, providerId],
  );

  const savedState = config.data?.providers[providerId];

  // Reset per-provider editor state when provider changes.
  useEffect(() => {
    if (!provider) return;
    const savedModel = savedState?.model ?? "";
    const defaultModel = provider.models[0] ?? "";
    const initial = savedModel || defaultModel;
    setModel(initial);
    setModelMode(
      initial && provider.models.includes(initial) ? "select" : "custom",
    );
    setBaseUrl(savedState?.base_url ?? provider.default_base_url ?? "");
    setApiKey("");
  }, [provider?.id, savedState?.model, savedState?.base_url]);

  if (providers.isLoading || config.isLoading) {
    return <Card>loading providers…</Card>;
  }
  if (providers.error || !providers.data) {
    return (
      <Card>
        <div style={{ color: "var(--signal-danger)" }}>
          failed to load providers
        </div>
      </Card>
    );
  }

  const isActive = providers.data.active_provider === providerId;
  const list = providers.data.providers;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 24 }}>
      <ProviderList
        list={list}
        activeProvider={providers.data.active_provider}
        configured={providers.data.configured}
        selected={providerId}
        onSelect={setProviderId}
      />

      {provider && (
        <Card ai>
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              justifyContent: "space-between",
              marginBottom: 8,
              gap: 12,
            }}
          >
            <div>
              <h3>{provider.label}</h3>
              {provider.notes && (
                <p
                  style={{
                    color: "var(--fg-muted)",
                    fontSize: 12,
                    marginTop: 4,
                  }}
                >
                  {provider.notes}
                </p>
              )}
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              {isActive && (
                <Pill tone="ai">
                  <Check size={10} /> active
                </Pill>
              )}
              {provider.has_key && !isActive && <Pill tone="info">key saved</Pill>}
            </div>
          </div>

          <div style={{ display: "grid", gap: 18, marginTop: 18 }}>
            {provider.requires_key && (
              <Field
                label="api key"
                hint={
                  provider.has_key
                    ? "leave blank to keep the saved key"
                    : "stored in OS keyring"
                }
              >
                <input
                  type="password"
                  className="mono"
                  value={apiKey}
                  placeholder={provider.has_key ? "•••••••• (saved)" : "sk-..."}
                  onChange={(e) => setApiKey(e.target.value)}
                />
              </Field>
            )}

            <Field
              label="model"
              hint={
                modelMode === "select"
                  ? "choose from this provider's catalog"
                  : "any model name the provider serves"
              }
            >
              {provider.models.length > 0 ? (
                <div style={{ display: "grid", gap: 6 }}>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      className={modelMode === "select" ? "primary" : "ghost"}
                      onClick={() => {
                        setModelMode("select");
                        if (!provider.models.includes(model)) {
                          setModel(provider.models[0]);
                        }
                      }}
                    >
                      catalog
                    </button>
                    <button
                      className={modelMode === "custom" ? "primary" : "ghost"}
                      onClick={() => setModelMode("custom")}
                    >
                      custom
                    </button>
                  </div>
                  {modelMode === "select" ? (
                    <select
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                    >
                      {provider.models.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      className="mono"
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      placeholder="org/custom-model"
                    />
                  )}
                </div>
              ) : (
                <input
                  className="mono"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="meta-llama/Llama-3.1-8B-Instruct"
                />
              )}
            </Field>

            <Field
              label="base url"
              hint={
                provider.base_url_editable
                  ? "where your server is listening"
                  : provider.default_base_url
                  ? `default: ${provider.default_base_url}`
                  : "n/a"
              }
            >
              <input
                className="mono"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder={provider.default_base_url ?? ""}
                disabled={!provider.base_url_editable && provider.family === "anthropic"}
              />
            </Field>

            <label
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                fontSize: 13,
                color: "var(--fg-secondary)",
              }}
            >
              <input
                type="checkbox"
                checked={makeActive}
                onChange={(e) => setMakeActive(e.target.checked)}
              />
              make this the active provider
            </label>
          </div>

          <div
            style={{
              marginTop: 22,
              paddingTop: 16,
              borderTop: "1px solid var(--border-subtle)",
              display: "flex",
              justifyContent: "flex-end",
              alignItems: "center",
              gap: 12,
            }}
          >
            {put.isSuccess && (
              <Pill tone="healthy">
                <Check size={10} /> saved
              </Pill>
            )}
            {put.error ? (
              <span
                style={{
                  color: "var(--signal-danger)",
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                }}
              >
                {put.error instanceof Error
                  ? put.error.message
                  : String(put.error)}
              </span>
            ) : null}
            <button
              className="primary"
              disabled={!model || put.isPending}
              onClick={() =>
                put.mutate({
                  provider: provider.id,
                  model: model.trim(),
                  base_url: baseUrl.trim() || null,
                  api_key: apiKey.trim() || undefined,
                  set_active: makeActive,
                })
              }
            >
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Save size={13} /> save
              </span>
            </button>
          </div>
        </Card>
      )}
    </div>
  );
}

function ProviderList({
  list,
  activeProvider,
  configured,
  selected,
  onSelect,
}: {
  list: ProviderDef[];
  activeProvider: string;
  configured: string[];
  selected: string;
  onSelect: (id: string) => void;
}) {
  return (
    <Card pad={0}>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--fg-muted)",
          letterSpacing: "0.14em",
          textTransform: "uppercase",
          padding: "12px 14px 8px",
        }}
      >
        providers
      </div>
      <div>
        {list.map((p) => {
          const isSel = p.id === selected;
          const isActive = p.id === activeProvider;
          const hasKey = p.has_key || configured.includes(p.id);
          return (
            <button
              key={p.id}
              className="ghost"
              onClick={() => onSelect(p.id)}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "10px 14px",
                borderRadius: 0,
                background: isSel ? "var(--bg-elev-3)" : "transparent",
                color: isSel ? "var(--fg-primary)" : "var(--fg-secondary)",
                borderLeft: isActive
                  ? "2px solid var(--accent-ai)"
                  : "2px solid transparent",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 8,
                }}
              >
                <span style={{ fontSize: 13 }}>{p.label}</span>
                <div style={{ display: "flex", gap: 4 }}>
                  {isActive && <Pill tone="ai">active</Pill>}
                  {!isActive && hasKey && <Pill tone="info">·</Pill>}
                  {!p.requires_key && !isActive && <Pill tone="neutral">local</Pill>}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </Card>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 6 }}>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--fg-muted)",
            letterSpacing: "0.16em",
            textTransform: "uppercase",
          }}
        >
          {label}
        </span>
        {hint && <span style={{ fontSize: 11, color: "var(--fg-faint)" }}>· {hint}</span>}
      </div>
      {children}
    </div>
  );
}
