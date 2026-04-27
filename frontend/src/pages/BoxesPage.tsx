import { Network, Server } from "lucide-react";
import { Link } from "react-router-dom";

import AddBoxDialog from "../components/AddBoxDialog";
import BoxList from "../components/BoxList";
import { Card, EmptyState, Pill } from "../components/Card";
import PageHeader from "../components/PageHeader";
import { useBoxes } from "../hooks/useBoxes";
import { useClusters } from "../hooks/useClusters";

export default function BoxesPage() {
  const { data, isLoading, error } = useBoxes();
  const clusters = useClusters();
  const boxes = data ?? [];
  const clusterList = clusters.data?.clusters ?? [];
  return (
    <>
      <PageHeader
        eyebrow="Fleet"
        title={
          <>
            DGX Spark <em style={{ fontStyle: "italic", color: "var(--fg-muted)" }}>boxes</em>
          </>
        }
        subtitle="Boxes you've registered with sparkd. Each one is a target for recipes and launches over SSH. Tag boxes with the same cluster name to form a multi-node group the Advisor can plan against."
      />

      <div style={{ display: "grid", gap: 24 }}>
        <Card pad={20}>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--fg-muted)",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              marginBottom: 12,
            }}
          >
            register a new box
          </div>
          <AddBoxDialog />
        </Card>

        {clusterList.length > 0 && (
          <div>
            <h4 style={{ marginBottom: 12 }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                <Network size={14} style={{ color: "var(--fg-muted)" }} />
                clusters
              </span>
            </h4>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
                gap: 12,
              }}
            >
              {clusterList.map((cl) => (
                <Card key={cl.name} pad={14}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      justifyContent: "space-between",
                      marginBottom: 8,
                    }}
                  >
                    <code
                      style={{
                        fontSize: 14,
                        fontWeight: 500,
                        color: "var(--fg-primary)",
                      }}
                    >
                      {cl.name}
                    </code>
                    <Pill tone="info">
                      {cl.box_count} node{cl.box_count === 1 ? "" : "s"}
                    </Pill>
                  </div>
                  <div style={{ display: "grid", gap: 4 }}>
                    {cl.boxes.map((b) => (
                      <Link
                        key={b.id}
                        to={`/boxes/${b.id}`}
                        style={{
                          borderBottom: "none",
                          color: "var(--fg-secondary)",
                          fontFamily: "var(--font-mono)",
                          fontSize: 12,
                        }}
                      >
                        · {b.name}
                      </Link>
                    ))}
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        <div>
          <h4 style={{ marginBottom: 12 }}>boxes</h4>
          <Card pad={0}>
            {isLoading ? (
              <div style={{ padding: 32, color: "var(--fg-muted)" }}>scanning…</div>
            ) : error ? (
              <div style={{ padding: 32, color: "var(--signal-danger)" }}>
                {String(error)}
              </div>
            ) : boxes.length === 0 ? (
              <EmptyState
                icon={<Server size={28} />}
                title="No boxes registered yet"
                hint="Add your first DGX Spark box above. SSH agent / key auth will be used."
              />
            ) : (
              <BoxList boxes={boxes} />
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
