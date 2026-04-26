import { Server } from "lucide-react";

import AddBoxDialog from "../components/AddBoxDialog";
import BoxList from "../components/BoxList";
import { Card, EmptyState } from "../components/Card";
import PageHeader from "../components/PageHeader";
import { useBoxes } from "../hooks/useBoxes";

export default function BoxesPage() {
  const { data, isLoading, error } = useBoxes();
  const boxes = data ?? [];
  return (
    <>
      <PageHeader
        eyebrow="Fleet"
        title={
          <>
            DGX Spark <em style={{ fontStyle: "italic", color: "var(--fg-muted)" }}>boxes</em>
          </>
        }
        subtitle="Boxes you've registered with sparkd. Each one is a target for recipes and launches over SSH."
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
    </>
  );
}
