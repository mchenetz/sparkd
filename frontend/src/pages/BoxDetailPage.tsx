import {
  Activity,
  ChevronLeft,
  Cpu,
  HardDrive,
  RefreshCw,
  Save,
  Trash2,
  Wifi,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Card, EmptyState, Pill } from "../components/Card";
import ChipInput from "../components/ChipInput";
import PageHeader from "../components/PageHeader";
import {
  Box,
  useBox,
  useBoxCapabilities,
  useDeleteBox,
  useRefreshBoxCapabilities,
  useTestBox,
  useUpdateBox,
} from "../hooks/useBoxes";
import { useBoxStatus } from "../hooks/useBoxStatus";
import { useClusters } from "../hooks/useClusters";
import { useLaunches } from "../hooks/useLaunches";

export default function BoxDetailPage() {
  const { id } = useParams<{ id: string }>();
  const boxQ = useBox(id ?? null);
  const capsQ = useBoxCapabilities(id ?? null);
  const refreshCaps = useRefreshBoxCapabilities();
  const updateBox = useUpdateBox();
  const del = useDeleteBox();
  const testBox = useTestBox();
  const navigate = useNavigate();

  const [draft, setDraft] = useState<Box | null>(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (boxQ.data) {
      setDraft(boxQ.data);
      setDirty(false);
    }
  }, [boxQ.data]);

  const status = useBoxStatus(id ?? null);
  const launches = useLaunches(id, { activeOnly: false });
  const clusters = useClusters();
  const knownClusters = (clusters.data?.clusters ?? []).map((c) => c.name);
  const launchesForBox = useMemo(
    () => (launches.data ?? []).filter((l) => l.box_id === id),
    [launches.data, id],
  );

  if (!id) return null;
  if (boxQ.isLoading || !draft) return <div>loading…</div>;
  if (boxQ.error)
    return (
      <div style={{ color: "var(--signal-danger)" }}>{String(boxQ.error)}</div>
    );

  const setField = <K extends keyof Box>(k: K, v: Box[K]) => {
    setDraft((d) => (d ? { ...d, [k]: v } : d));
    setDirty(true);
  };

  return (
    <>
      <PageHeader
        eyebrow={
          <Link to="/" style={{ borderBottom: "none" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <ChevronLeft size={12} /> Boxes
            </span>
          </Link>
        }
        title={
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 28 }}>
            {draft.name}
          </span>
        }
        subtitle={
          <code style={{ color: "var(--fg-secondary)" }}>
            {draft.user}@{draft.host}:{draft.port}
          </code>
        }
        actions={
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {status && (
              <Pill
                tone={
                  status.connectivity === "online"
                    ? "healthy"
                    : status.connectivity === "degraded"
                    ? "warn"
                    : "danger"
                }
              >
                <Activity size={10} /> {status.connectivity}
              </Pill>
            )}
            <button
              className="ghost"
              disabled={testBox.isPending}
              onClick={() => testBox.mutate(id)}
            >
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Wifi size={13} />
                {testBox.isPending
                  ? "testing…"
                  : testBox.data?.ok
                  ? "ssh ok"
                  : testBox.data?.ok === false
                  ? "ssh fail"
                  : "test ssh"}
              </span>
            </button>
            <button
              className="danger"
              onClick={async () => {
                if (!confirm(`Delete box ${draft.name}?`)) return;
                await del.mutateAsync(id);
                navigate("/");
              }}
            >
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Trash2 size={13} /> delete
              </span>
            </button>
          </div>
        }
      />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
          alignItems: "start",
        }}
      >
        <Card>
          <h4 style={{ marginBottom: 14 }}>connection</h4>
          <div style={{ display: "grid", gap: 14 }}>
            <Field label="name">
              <input
                value={draft.name}
                onChange={(e) => setField("name", e.target.value)}
              />
            </Field>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 80px",
                gap: 8,
              }}
            >
              <Field label="host">
                <input
                  className="mono"
                  value={draft.host}
                  onChange={(e) => setField("host", e.target.value)}
                />
              </Field>
              <Field label="port">
                <input
                  className="mono"
                  value={String(draft.port)}
                  onChange={(e) =>
                    setField(
                      "port",
                      Number(e.target.value.replace(/[^0-9]/g, "") || 22),
                    )
                  }
                />
              </Field>
            </div>
            <Field label="user">
              <input
                className="mono"
                value={draft.user}
                onChange={(e) => setField("user", e.target.value)}
              />
            </Field>
            <Field label="repo path" hint="path to spark-vllm-docker on the box">
              <input
                className="mono"
                value={draft.repo_path}
                onChange={(e) => setField("repo_path", e.target.value)}
              />
            </Field>
            <Field
              label="cluster"
              hint="boxes sharing a cluster name form a multi-node group"
            >
              <ChipInput
                value={draft.tags?.cluster ?? ""}
                onChange={(next) => {
                  const tags = { ...(draft.tags ?? {}) };
                  if (next) tags.cluster = next;
                  else delete tags.cluster;
                  setField("tags", tags);
                }}
                suggestions={knownClusters}
                placeholder="alpha"
              />
            </Field>
            <Field
              label="cluster ip"
              hint="LOCAL_IP from upstream's .env — used as the -n value for cluster launches. Auto-detected on capabilities refresh."
            >
              <input
                className="mono"
                value={draft.cluster_ip ?? ""}
                onChange={(e) =>
                  setField("cluster_ip", e.target.value || null)
                }
                placeholder="192.168.201.10"
              />
            </Field>
            <Field label="ssh auth">
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
                  checked={draft.use_agent}
                  onChange={(e) => setField("use_agent", e.target.checked)}
                />
                use ssh agent (recommended)
              </label>
              {!draft.use_agent && (
                <input
                  className="mono"
                  value={draft.ssh_key_path ?? ""}
                  onChange={(e) => setField("ssh_key_path", e.target.value)}
                  placeholder="~/.ssh/id_ed25519"
                  style={{ marginTop: 6 }}
                />
              )}
            </Field>
            <div
              style={{
                display: "flex",
                gap: 10,
                paddingTop: 10,
                borderTop: "1px solid var(--border-subtle)",
                alignItems: "center",
                justifyContent: "flex-end",
              }}
            >
              {dirty && <Pill tone="warn">unsaved</Pill>}
              <button
                className="primary"
                disabled={!dirty || updateBox.isPending}
                onClick={async () => {
                  await updateBox.mutateAsync({ id, body: draft });
                  setDirty(false);
                }}
              >
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <Save size={13} /> save
                </span>
              </button>
            </div>
          </div>
        </Card>

        <div style={{ display: "grid", gap: 16 }}>
          <Card>
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                justifyContent: "space-between",
                marginBottom: 12,
              }}
            >
              <h4 style={{ margin: 0 }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                  <Cpu size={14} style={{ color: "var(--fg-muted)" }} />
                  hardware
                </span>
              </h4>
              <button
                className="ghost"
                disabled={refreshCaps.isPending}
                onClick={() => refreshCaps.mutate(id)}
              >
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <RefreshCw size={12} />
                  {refreshCaps.isPending ? "refreshing…" : "refresh"}
                </span>
              </button>
            </div>
            {capsQ.isLoading ? (
              <div style={{ color: "var(--fg-muted)" }}>fetching…</div>
            ) : capsQ.error ? (
              <div style={{ color: "var(--signal-danger)" }}>
                {String(capsQ.error)}
              </div>
            ) : capsQ.data ? (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "auto 1fr",
                  gap: "6px 14px",
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                }}
              >
                <span style={{ color: "var(--fg-muted)" }}>gpu count</span>
                <span>{capsQ.data.gpu_count}</span>
                <span style={{ color: "var(--fg-muted)" }}>gpu model</span>
                <span>{capsQ.data.gpu_model || "—"}</span>
                <span style={{ color: "var(--fg-muted)" }}>vram per gpu</span>
                <span>
                  {capsQ.data.vram_per_gpu_gb > 0
                    ? `${capsQ.data.vram_per_gpu_gb} GB`
                    : "—"}
                </span>
                <span style={{ color: "var(--fg-muted)" }}>cuda</span>
                <span>{capsQ.data.cuda_version || "—"}</span>
                <span style={{ color: "var(--fg-muted)" }}>infiniband</span>
                <span>{capsQ.data.ib_interface || "—"}</span>
                <span style={{ color: "var(--fg-muted)" }}>captured</span>
                <span style={{ color: "var(--fg-faint)" }}>
                  {new Date(capsQ.data.captured_at).toLocaleString()}
                </span>
              </div>
            ) : null}
          </Card>

          <Card>
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                justifyContent: "space-between",
                marginBottom: 12,
              }}
            >
              <h4 style={{ margin: 0 }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                  <HardDrive size={14} style={{ color: "var(--fg-muted)" }} />
                  running
                </span>
              </h4>
              {status && (
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: "var(--fg-faint)",
                  }}
                >
                  captured{" "}
                  {new Date(status.captured_at).toLocaleTimeString()}
                </span>
              )}
            </div>
            {!status ? (
              <div style={{ color: "var(--fg-muted)" }}>connecting…</div>
            ) : status.running_models.length === 0 ? (
              <EmptyState title="No containers running" />
            ) : (
              <div style={{ display: "grid", gap: 6 }}>
                {status.running_models.map((m) => (
                  <div
                    key={m.container_id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      fontFamily: "var(--font-mono)",
                      fontSize: 12,
                    }}
                  >
                    <Pill tone={m.healthy ? "healthy" : "warn"}>
                      {m.healthy ? "200" : "down"}
                    </Pill>
                    <code>{m.container_id.slice(0, 12)}</code>
                    {m.recipe_name ? (
                      <span>{m.recipe_name}</span>
                    ) : (
                      <span style={{ color: "var(--fg-faint)" }}>—</span>
                    )}
                    <Pill tone={m.source === "dashboard" ? "info" : "neutral"}>
                      {m.source}
                    </Pill>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      <Card style={{ marginTop: 24 }} pad={0}>
        <div
          style={{
            padding: "12px 16px",
            borderBottom: "1px solid var(--border-subtle)",
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
          }}
        >
          <h4 style={{ margin: 0 }}>launches on this box</h4>
          <Link to="/launch" style={{ borderBottom: "none" }}>
            <button className="ghost">open Launch →</button>
          </Link>
        </div>
        {launchesForBox.length === 0 ? (
          <div
            style={{
              padding: 24,
              color: "var(--fg-muted)",
              textAlign: "center",
              fontStyle: "italic",
            }}
          >
            none yet
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>recipe</th>
                <th>state</th>
                <th>container</th>
                <th>started</th>
              </tr>
            </thead>
            <tbody>
              {launchesForBox.map((l) => (
                <tr key={l.id}>
                  <td>
                    <Link
                      to={`/recipes/${encodeURIComponent(l.recipe_name)}`}
                      style={{ borderBottom: "none" }}
                    >
                      <span style={{ fontWeight: 500 }}>{l.recipe_name}</span>
                    </Link>
                  </td>
                  <td>
                    <Pill
                      tone={
                        l.state === "healthy"
                          ? "healthy"
                          : l.state === "paused"
                          ? "info"
                          : l.state === "failed"
                          ? "danger"
                          : l.state === "starting"
                          ? "warn"
                          : "neutral"
                      }
                    >
                      {l.state}
                    </Pill>
                  </td>
                  <td>
                    <code style={{ color: "var(--fg-muted)" }}>
                      {l.container_id?.slice(0, 12) ?? "—"}
                    </code>
                  </td>
                  <td>
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        color: "var(--fg-faint)",
                      }}
                    >
                      {new Date(l.started_at).toLocaleString()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
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
