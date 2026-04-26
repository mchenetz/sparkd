import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Boxes,
  CircleHelp,
  FlaskConical,
  Network,
  Rocket,
  Sparkles,
  Wrench,
} from "lucide-react";
import { ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { api } from "../api/client";

type Health = { db: string; ssh_pool_size: number; sparkd_home: string };

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: 999,
        background: ok ? "var(--signal-healthy)" : "var(--signal-danger)",
        color: ok ? "var(--signal-healthy)" : "var(--signal-danger)",
        animation: "pulse-dot 2.4s var(--ease-in-out) infinite",
        boxShadow: ok ? "0 0 8px currentColor" : "0 0 6px currentColor",
      }}
    />
  );
}

function TopBar() {
  const health = useQuery({
    queryKey: ["healthz"],
    queryFn: () => api.get<Health>("/healthz"),
    refetchInterval: 5000,
  });
  const ok = !!health.data && health.data.db === "ok";
  const home = health.data?.sparkd_home ?? "—";
  return (
    <header
      style={{
        height: "var(--topbar-h)",
        borderBottom: "1px solid var(--border-subtle)",
        background: "var(--bg-elev-1)",
        display: "flex",
        alignItems: "center",
        padding: "0 20px",
        gap: 16,
        position: "sticky",
        top: 0,
        zIndex: 10,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <StatusDot ok={ok} />
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: ok ? "var(--signal-healthy)" : "var(--signal-danger)",
          }}
        >
          {ok ? "operational" : "degraded"}
        </span>
      </div>
      <div style={{ width: 1, height: 16, background: "var(--border-subtle)" }} />
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--fg-muted)",
        }}
      >
        ssh.pool={health.data?.ssh_pool_size ?? 0}
      </span>
      <div style={{ flex: 1 }} />
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--fg-faint)",
        }}
        title={home}
      >
        {home.replace(/^.*\/(?=[^/]+\/?$)/, "…/")}
      </span>
    </header>
  );
}

const NAV: Array<{
  to: string;
  label: string;
  icon: ReactNode;
  group: "ops" | "ai";
}> = [
  { to: "/", label: "Boxes", icon: <Network size={16} />, group: "ops" },
  { to: "/recipes", label: "Recipes", icon: <FlaskConical size={16} />, group: "ops" },
  { to: "/launch", label: "Launch", icon: <Rocket size={16} />, group: "ops" },
  { to: "/status", label: "Status", icon: <Activity size={16} />, group: "ops" },
  { to: "/advisor", label: "Advisor", icon: <Sparkles size={16} />, group: "ai" },
  { to: "/optimize", label: "Optimize", icon: <Wrench size={16} />, group: "ai" },
  { to: "/mods", label: "Mods", icon: <Boxes size={16} />, group: "ai" },
];

function Sidebar() {
  return (
    <aside
      style={{
        width: "var(--sidebar-w)",
        borderRight: "1px solid var(--border-subtle)",
        background: "var(--bg-elev-1)",
        height: "100vh",
        position: "sticky",
        top: 0,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          padding: "20px 20px 24px",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <div
          style={{
            fontFamily: "var(--font-display)",
            fontStyle: "italic",
            fontSize: 28,
            letterSpacing: "-0.02em",
            lineHeight: 1,
          }}
        >
          sparkd
        </div>
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: "var(--fg-faint)",
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            marginTop: 6,
          }}
        >
          DGX Spark · vLLM
        </div>
      </div>

      <nav style={{ padding: 12, display: "flex", flexDirection: "column", gap: 2 }}>
        <SectionLabel>Operations</SectionLabel>
        {NAV.filter((n) => n.group === "ops").map((n) => (
          <NavItem key={n.to} {...n} />
        ))}
        <div style={{ height: 14 }} />
        <SectionLabel>AI Advisor</SectionLabel>
        {NAV.filter((n) => n.group === "ai").map((n) => (
          <NavItem key={n.to} {...n} />
        ))}
      </nav>

      <div style={{ flex: 1 }} />

      <div
        style={{
          padding: "14px 20px",
          borderTop: "1px solid var(--border-subtle)",
          fontFamily: "var(--font-mono)",
          fontSize: 10.5,
          color: "var(--fg-faint)",
          letterSpacing: "0.1em",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <CircleHelp size={11} />
          <span>localhost:8765</span>
        </div>
      </div>
    </aside>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        padding: "8px 12px 6px",
        fontSize: 10,
        fontFamily: "var(--font-mono)",
        textTransform: "uppercase",
        letterSpacing: "0.18em",
        color: "var(--fg-faint)",
      }}
    >
      {children}
    </div>
  );
}

function NavItem({
  to,
  label,
  icon,
  group,
}: {
  to: string;
  label: string;
  icon: ReactNode;
  group: "ops" | "ai";
}) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      style={({ isActive }) => ({
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "9px 12px",
        borderRadius: "var(--radius-sm)",
        fontSize: 13,
        color: isActive ? "var(--fg-primary)" : "var(--fg-secondary)",
        background: isActive ? "var(--bg-elev-3)" : "transparent",
        borderBottom: "none",
        position: "relative",
        transition: "all 140ms var(--ease-out)",
      })}
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span
              style={{
                position: "absolute",
                left: 0,
                top: 8,
                bottom: 8,
                width: 2,
                background: group === "ai" ? "var(--accent-ai)" : "var(--signal-healthy)",
                borderRadius: 1,
              }}
            />
          )}
          <span
            style={{
              color: isActive
                ? group === "ai"
                  ? "var(--accent-ai)"
                  : "var(--fg-primary)"
                : "var(--fg-muted)",
              display: "flex",
            }}
          >
            {icon}
          </span>
          {label}
        </>
      )}
    </NavLink>
  );
}

export default function Shell({ children }: { children: ReactNode }) {
  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <Sidebar />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <TopBar />
        <main
          style={{
            padding: "var(--content-pad)",
            maxWidth: "var(--content-max)",
            width: "100%",
            margin: "0 auto",
            animation: "sweep-in 360ms var(--ease-out)",
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
