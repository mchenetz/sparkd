import {
  AlertCircle,
  Cpu,
  Network,
  Radio,
  Server,
} from "lucide-react";
import { Link } from "react-router-dom";

import { Card, EmptyState, Pill } from "../components/Card";
import PageHeader from "../components/PageHeader";
import {
  FleetCluster,
  FleetLaunch,
  FleetMember,
  FleetStandalone,
  useFleetStatus,
} from "../hooks/useFleetStatus";

const STATE_TONE: Record<
  FleetLaunch["state"],
  "healthy" | "warn" | "danger" | "neutral" | "info"
> = {
  starting: "warn",
  healthy: "healthy",
  paused: "info",
  failed: "danger",
  stopped: "neutral",
  interrupted: "danger",
};

export default function StatusPage() {
  const { data: snap, isLoading, error } = useFleetStatus();

  const empty =
    snap &&
    snap.clusters.length === 0 &&
    snap.standalones.length === 0 &&
    snap.drift_external_containers.length === 0 &&
    snap.drift_orphan_launches.length === 0;

  return (
    <>
      <PageHeader
        eyebrow="Telemetry"
        title={
          <>
            Fleet <em style={{ color: "var(--fg-muted)" }}>status</em>
          </>
        }
        subtitle="One-shot view of clusters, standalones, and drift across every registered box. Driven by the launch reconciler — refreshes every 5s."
      />

      {isLoading && !snap ? (
        <Card>
          <div style={{ color: "var(--fg-muted)" }}>
            <span
              style={{
                display: "inline-block",
                width: 8,
                height: 8,
                borderRadius: 999,
                background: "var(--signal-info)",
                marginRight: 8,
                animation: "pulse-dot 1.4s var(--ease-in-out) infinite",
              }}
            />
            loading fleet snapshot…
          </div>
        </Card>
      ) : error ? (
        <Card>
          <div style={{ color: "var(--signal-danger)" }}>
            failed to load fleet status: {String(error)}
          </div>
        </Card>
      ) : empty ? (
        <EmptyState
          icon={<Server size={28} />}
          title="No registered boxes"
          hint="Add a box on the Boxes page to start populating the fleet."
        />
      ) : snap ? (
        <div style={{ display: "grid", gap: 24 }}>
          {snap.clusters.length > 0 && (
            <Section title="Clusters" icon={<Network size={14} />}>
              <div style={{ display: "grid", gap: 12 }}>
                {snap.clusters.map((c) => (
                  <ClusterCard key={c.name} cluster={c} />
                ))}
              </div>
            </Section>
          )}

          {snap.standalones.length > 0 && (
            <Section title="Standalone boxes" icon={<Server size={14} />}>
              <div style={{ display: "grid", gap: 12 }}>
                {snap.standalones.map((s) => (
                  <StandaloneCard
                    key={s.member.box_id}
                    standalone={s}
                  />
                ))}
              </div>
            </Section>
          )}

          {(snap.drift_external_containers.length > 0 ||
            snap.drift_orphan_launches.length > 0) && (
            <Section
              title="Drift"
              icon={
                <AlertCircle
                  size={14}
                  style={{ color: "var(--signal-warn)" }}
                />
              }
            >
              <DriftCard snap={snap} />
            </Section>
          )}

          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--fg-faint)",
              textAlign: "right",
            }}
          >
            captured_at {new Date(snap.captured_at).toLocaleTimeString()}
          </div>
        </div>
      ) : null}
    </>
  );
}

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h4
        style={{
          marginBottom: 12,
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        {icon}
        {title}
      </h4>
      {children}
    </div>
  );
}

function ClusterCard({ cluster }: { cluster: FleetCluster }) {
  return (
    <Card pad={16}>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 12,
          marginBottom: 12,
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <code
            style={{
              fontSize: 14,
              fontWeight: 500,
              color: "var(--fg-primary)",
            }}
          >
            {cluster.name}
          </code>
          <Pill tone="info">
            {cluster.members.length} node
            {cluster.members.length === 1 ? "" : "s"}
          </Pill>
        </div>
        <ActiveLaunchSummary launch={cluster.active_launch} />
      </div>
      <div style={{ display: "grid", gap: 4 }}>
        {cluster.members.map((m) => (
          <MemberRow
            key={m.box_id}
            member={m}
            hasActiveLaunch={!!cluster.active_launch}
          />
        ))}
      </div>
    </Card>
  );
}

function StandaloneCard({ standalone }: { standalone: FleetStandalone }) {
  return (
    <Card pad={16}>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
          <ConnectivityDot connectivity={standalone.member.connectivity} />
          <Link
            to={`/boxes/${standalone.member.box_id}`}
            style={{ borderBottom: "none", color: "var(--fg-primary)" }}
          >
            <code style={{ fontSize: 14, fontWeight: 500 }}>
              {standalone.member.box_name}
            </code>
          </Link>
          <Pill
            tone={
              standalone.member.connectivity === "online" ? "healthy" : "danger"
            }
          >
            <Radio size={9} /> {standalone.member.connectivity}
          </Pill>
        </div>
        <ActiveLaunchSummary launch={standalone.active_launch} />
      </div>
      {standalone.member.container_id && (
        <div
          style={{
            marginTop: 8,
            paddingTop: 8,
            borderTop: "1px solid var(--border-subtle)",
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--fg-muted)",
          }}
        >
          container <code>{standalone.member.container_id.slice(0, 12)}</code>
          {standalone.member.container_image && (
            <span style={{ marginLeft: 12 }}>
              image <code>{standalone.member.container_image}</code>
            </span>
          )}
        </div>
      )}
    </Card>
  );
}

function MemberRow({
  member,
  hasActiveLaunch,
}: {
  member: FleetMember;
  hasActiveLaunch: boolean;
}) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr auto auto",
        alignItems: "center",
        gap: 10,
        padding: "6px 8px",
        borderRadius: "var(--radius-sm)",
        background: "var(--bg-elev-1)",
        fontSize: 12,
      }}
    >
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 10,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color:
            member.role === "head"
              ? "var(--signal-info)"
              : "var(--fg-muted)",
          minWidth: 56,
        }}
      >
        {member.role === "head" ? "· head" : "· worker"}
      </span>
      <Link
        to={`/boxes/${member.box_id}`}
        style={{
          borderBottom: "none",
          color: "var(--fg-secondary)",
          fontFamily: "var(--font-mono)",
          fontSize: 12,
        }}
      >
        {member.box_name}
      </Link>
      <ConnectivityDot connectivity={member.connectivity} />
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--fg-faint)",
          minWidth: 130,
          textAlign: "right",
        }}
      >
        {member.container_id ? (
          <>
            <Cpu
              size={10}
              style={{
                verticalAlign: "middle",
                marginRight: 4,
                color: "var(--fg-muted)",
              }}
            />
            {member.container_id.slice(0, 12)}
          </>
        ) : member.role === "worker" && hasActiveLaunch ? (
          <span style={{ color: "var(--fg-faint)" }}>(via head)</span>
        ) : (
          <span style={{ color: "var(--fg-faint)" }}>—</span>
        )}
      </span>
    </div>
  );
}

function ActiveLaunchSummary({ launch }: { launch: FleetLaunch | null }) {
  if (!launch) {
    return (
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--fg-faint)",
          letterSpacing: "0.06em",
          textTransform: "uppercase",
        }}
      >
        ◯ idle — no active launch
      </span>
    );
  }
  const startedMs = new Date(launch.started_at).getTime();
  const ageS = Math.max(0, Math.floor((Date.now() - startedMs) / 1000));
  const age =
    ageS < 60
      ? `${ageS}s`
      : ageS < 3600
        ? `${Math.floor(ageS / 60)}m${ageS % 60}s`
        : `${Math.floor(ageS / 3600)}h${Math.floor((ageS % 3600) / 60)}m`;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <Pill tone={STATE_TONE[launch.state]}>{launch.state}</Pill>
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 12,
          color: "var(--fg-secondary)",
        }}
      >
        {launch.recipe_name}
      </span>
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--fg-faint)",
        }}
      >
        ({age})
      </span>
    </span>
  );
}

function ConnectivityDot({
  connectivity,
}: {
  connectivity: FleetMember["connectivity"];
}) {
  const color =
    connectivity === "online"
      ? "var(--signal-healthy)"
      : connectivity === "offline"
        ? "var(--signal-danger)"
        : "var(--fg-muted)";
  return (
    <span
      title={connectivity}
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: 999,
        background: color,
      }}
    />
  );
}

function DriftCard({
  snap,
}: {
  snap: { drift_external_containers: any[]; drift_orphan_launches: string[] };
}) {
  return (
    <Card pad={16}>
      <p
        style={{
          color: "var(--fg-secondary)",
          fontSize: 12,
          margin: 0,
          marginBottom: 10,
        }}
      >
        Things that don't reconcile against the launch DB. Most often this
        means a container was started by hand, or a launch's container was
        cleaned up externally — the reconciler will catch up on its next
        tick (~5s).
      </p>
      {snap.drift_external_containers.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--fg-muted)",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              marginBottom: 6,
            }}
          >
            external containers
          </div>
          {snap.drift_external_containers.map((d: any) => (
            <div
              key={`${d.box_id}-${d.container_id}`}
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                color: "var(--fg-secondary)",
                padding: "4px 0",
              }}
            >
              · {d.box_name}: <code>{d.container_id}</code>{" "}
              <span style={{ color: "var(--fg-muted)" }}>
                ({d.image}, {d.state})
              </span>
            </div>
          ))}
        </div>
      )}
      {snap.drift_orphan_launches.length > 0 && (
        <div>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--fg-muted)",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              marginBottom: 6,
            }}
          >
            orphan launches
          </div>
          {snap.drift_orphan_launches.map((id) => (
            <div
              key={id}
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                color: "var(--fg-secondary)",
                padding: "4px 0",
              }}
            >
              · launch <code>{id}</code>{" "}
              <span style={{ color: "var(--fg-muted)" }}>
                — container missing on head
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
