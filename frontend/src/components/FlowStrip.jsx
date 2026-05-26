/**
 * FlowStrip — animated 5-node pipeline visualisation.
 *
 * Polls GET /api/v1/audits?limit=1&sort=desc every 3 seconds.
 * When status changes running→completed, animates each node in sequence.
 * Nodes: idle (gray) | active (teal pulse) | done (teal solid)
 */
import React, { useEffect, useState, useRef } from "react";
import { fetchLatestAudit } from "../api/saro";

const NODES = [
  { id: "vendor",  label: "AI Vendor",    sub: "openai / claude / grok" },
  { id: "ingest",  label: "/ingest",       sub: "FastAPI POST" },
  { id: "engine",  label: "Engine Router", sub: "4-gate pipeline" },
  { id: "trace",   label: "TRACE",         sub: "Evidence log" },
  { id: "score",   label: "Risk Score",    sub: "MIT coverage" },
];

export default function FlowStrip({ token }) {
  const [nodeStates, setNodeStates] = useState(
    NODES.reduce((acc, n) => ({ ...acc, [n.id]: "idle" }), {})
  );
  const lastStatusRef = useRef(null);

  useEffect(() => {
    if (!token) return;
    const poll = setInterval(async () => {
      try {
        const data = await fetchLatestAudit(token);
        const audit = Array.isArray(data) ? data[0] : data;
        if (!audit) return;

        const prev = lastStatusRef.current;
        const curr = audit.status;

        if (prev === "running" && curr === "completed") {
          // Animate nodes in sequence on completion
          NODES.forEach((node, i) => {
            setTimeout(() => {
              setNodeStates((s) => ({ ...s, [node.id]: i < NODES.length - 1 ? "done" : "active" }));
            }, i * 300);
          });
          setTimeout(() => {
            setNodeStates(NODES.reduce((acc, n) => ({ ...acc, [n.id]: "done" }), {}));
          }, NODES.length * 300 + 200);
        } else if (curr === "running") {
          setNodeStates((s) => ({
            ...s,
            vendor: "done",
            ingest: "active",
          }));
        }
        lastStatusRef.current = curr;
      } catch (e) {
        // Ignore poll errors silently
      }
    }, 3000);
    return () => clearInterval(poll);
  }, [token]);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 0" }}>
      {NODES.map((node, i) => (
        <React.Fragment key={node.id}>
          <div
            style={{
              padding: "8px 12px",
              borderRadius: 8,
              background:
                nodeStates[node.id] === "done"
                  ? "#0d9488"
                  : nodeStates[node.id] === "active"
                  ? "#5eead4"
                  : "#e5e7eb",
              color: nodeStates[node.id] !== "idle" ? "#fff" : "#374151",
              minWidth: 100,
              textAlign: "center",
              transition: "background 0.4s",
            }}
          >
            <div style={{ fontWeight: 600, fontSize: 13 }}>{node.label}</div>
            <div style={{ fontSize: 11, opacity: 0.8 }}>{node.sub}</div>
          </div>
          {i < NODES.length - 1 && (
            <div style={{ color: "#9ca3af", fontSize: 18 }}>→</div>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}
