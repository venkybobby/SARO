import React, { useEffect, useState, useMemo } from "react";
import {
  Search, Plus, Eye, Edit2, Trash2, ChevronUp, ChevronDown,
  ChevronsUpDown, User, Tag, ShieldOff, ArrowLeft, ArrowRight,
} from "lucide-react";
import { Badge, Button, EmptyState, IconButton, Skeleton, ConfirmDialog, PageHeader } from "../components/ui/index.jsx";


const PAGE_SIZE_OPTIONS = [25, 50, 100];

function SortIcon({ active, direction }) {
  if (!active) return <ChevronsUpDown size={12} style={{ opacity: 0.3 }} />;
  return direction === "asc" ? <ChevronUp size={12} /> : <ChevronDown size={12} />;
}

function isOverdue(dueDate) {
  return new Date(dueDate) < new Date();
}

export default function RiskRegister({ token, onNavigate }) {
  const [risks,       setRisks]       = useState([]);
  const [search,      setSearch]      = useState("");
  const [sortKey,     setSortKey]     = useState("severity");
  const [sortDir,     setSortDir]     = useState("desc");
  const [page,        setPage]        = useState(1);
  const [pageSize,    setPageSize]    = useState(25);
  const [selectedIds, setSelectedIds] = useState([]);
  const [deleteId,    setDeleteId]    = useState(null);
  const [loading,     setLoading]     = useState(true);
  const [fetchError,  setFetchError]  = useState(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setFetchError(null);
      try {
        const r = await fetch("/api/v1/risks", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) throw new Error(`${r.status}`);
        setRisks(await r.json());
      } catch (e) {
        setFetchError(`Could not load risks from API: ${e.message}`);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token]);

  const SEV_ORDER = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return risks.filter((r) =>
      !q ||
      r.title.toLowerCase().includes(q) ||
      r.id.toLowerCase().includes(q) ||
      r.owner.toLowerCase().includes(q)
    );
  }, [search, risks]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "severity") cmp = (SEV_ORDER[a.severity] ?? 99) - (SEV_ORDER[b.severity] ?? 99);
      else if (sortKey === "dueDate") cmp = new Date(a.dueDate) - new Date(b.dueDate);
      else cmp = String(a[sortKey]).localeCompare(String(b[sortKey]));
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [filtered, sortKey, sortDir]);

  const totalPages = Math.ceil(sorted.length / pageSize) || 1;
  const paginated  = sorted.slice((page - 1) * pageSize, page * pageSize);

  function handleSort(key) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  }

  function toggleSelect(id) {
    setSelectedIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
  }

  function toggleSelectAll() {
    setSelectedIds((prev) => prev.length === paginated.length ? [] : paginated.map((r) => r.id));
  }

  const thStyle = (key) => ({
    padding: "var(--space-2) var(--space-3)",
    fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
    color: "var(--color-text-muted)", textTransform: "uppercase",
    letterSpacing: "0.06em", textAlign: "left", whiteSpace: "nowrap",
    cursor: "pointer", userSelect: "none", fontFamily: "var(--font-display)",
    background: "var(--color-bg-surface)",
    borderBottom: "1px solid var(--color-border-subtle)",
  });

  return (
    <div style={{ background: "var(--color-bg-base)", minHeight: "100vh" }}>
      <PageHeader
        title="Risk Register"
        subtitle={`${sorted.length} risks`}
        breadcrumb={<><span>Dashboard</span><span style={{ color: "var(--color-text-muted)" }}> › </span><span>Risk Register</span></>}
        actions={<Button variant="primary" size="sm" onClick={() => onNavigate?.("risk_form")}><Plus size={14} /> New Risk</Button>}
      />

      {/* Toolbar */}
      <div style={{
        padding: "var(--space-4) var(--space-6)",
        borderBottom: "1px solid var(--color-border-subtle)",
        background: "var(--color-bg-surface)",
        display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap",
      }}>
        <div style={{ position: "relative", flex: 1, minWidth: 240, maxWidth: 480 }}>
          <Search size={14} style={{
            position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)",
            color: "var(--color-text-muted)",
          }} />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search risks by title, ID, owner…"
            autoFocus
            style={{
              width: "100%", paddingLeft: 30, paddingRight: 12,
              paddingTop: 8, paddingBottom: 8,
              background: "var(--color-bg-elevated)",
              border: "1px solid var(--color-border-default)",
              borderRadius: "var(--radius-md)",
              color: "var(--color-text-primary)", fontSize: "var(--text-sm)",
              fontFamily: "var(--font-body)", outline: "none",
            }}
            onFocus={(e) => { e.target.style.borderColor = "var(--color-info)"; e.target.style.boxShadow = "var(--focus-ring)"; }}
            onBlur={(e) => { e.target.style.borderColor = "var(--color-border-default)"; e.target.style.boxShadow = "none"; }}
          />
        </div>
      </div>

      {/* Bulk action bar */}
      {selectedIds.length > 0 && (
        <div style={{
          padding: "var(--space-2) var(--space-6)",
          background: "var(--color-info-bg)",
          border: "1px solid var(--color-info-border)",
          display: "flex", alignItems: "center", gap: "var(--space-3)",
        }}>
          <span style={{ fontSize: "var(--text-sm)", color: "var(--color-info)", fontWeight: "var(--weight-medium)" }}>
            {selectedIds.length} selected
          </span>
          <Button variant="ghost" size="sm"><User size={13} /> Assign owner</Button>
          <Button variant="ghost" size="sm"><Tag size={13} /> Change status</Button>
          <Button variant="danger" size="sm"><Trash2 size={13} /> Delete</Button>
          <Button variant="ghost" size="sm" onClick={() => setSelectedIds([])}>Clear</Button>
        </div>
      )}

      {fetchError && (
        <div style={{ padding: "var(--space-3) var(--space-6)", background: "#fffbeb", borderBottom: "1px solid #fde68a", fontSize: "var(--text-sm)", color: "#92400e" }}>
          {fetchError}
        </div>
      )}

      {/* Table */}
      <div style={{ overflowX: "auto" }}>
        {loading ? (
          <div style={{ padding: "var(--space-6)" }}>
            {[...Array(5)].map((_, i) => <Skeleton key={i} height={40} style={{ marginBottom: "var(--space-2)" }} />)}
          </div>
        ) : sorted.length === 0 ? (
          <EmptyState
            icon={<ShieldOff />}
            title="No risks found"
            description={search ? "Try adjusting your search." : "Add your first risk to start tracking your risk posture."}
            action={!search && <Button variant="primary" size="sm" onClick={() => onNavigate?.("risk_form")}><Plus size={13} /> Add risk</Button>}
          />
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 700 }}>
            <thead>
              <tr>
                <th style={{ ...thStyle(), width: 36 }}>
                  <input
                    type="checkbox"
                    checked={selectedIds.length === paginated.length && paginated.length > 0}
                    onChange={toggleSelectAll}
                    style={{ cursor: "pointer" }}
                  />
                </th>
                {[
                  { key: "id",       label: "Risk ID",  width: 80 },
                  { key: "title",    label: "Title",    width: null },
                  { key: "category", label: "Category", width: 130 },
                  { key: "severity", label: "Severity", width: 110 },
                  { key: "owner",    label: "Owner",    width: 130 },
                  { key: "dueDate",  label: "Due Date", width: 110 },
                  { key: "status",   label: "Status",   width: 110 },
                ].map(({ key, label, width }) => (
                  <th
                    key={key}
                    style={{ ...thStyle(key), width: width || undefined }}
                    onClick={() => handleSort(key)}
                    aria-sort={sortKey === key ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
                  >
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                      {label}
                      <SortIcon active={sortKey === key} direction={sortDir} />
                    </span>
                  </th>
                ))}
                <th style={{ ...thStyle(), width: 90 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {paginated.map((risk, idx) => (
                <tr
                  key={risk.id}
                  style={{
                    background: idx % 2 === 0 ? "var(--color-bg-base)" : "var(--color-bg-surface)",
                    borderBottom: "1px solid var(--color-border-subtle)",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "var(--color-bg-elevated)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = idx % 2 === 0 ? "var(--color-bg-base)" : "var(--color-bg-surface)"; }}
                >
                  <td style={{ padding: "var(--space-3)", width: 36 }}>
                    <input type="checkbox" checked={selectedIds.includes(risk.id)} onChange={() => toggleSelect(risk.id)} style={{ cursor: "pointer" }} />
                  </td>
                  <td style={{ padding: "var(--space-3)", width: 80 }}>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                      {risk.id}
                    </span>
                  </td>
                  <td style={{ padding: "var(--space-3)", maxWidth: 280 }}>
                    <span style={{
                      fontSize: "var(--text-sm)", color: "var(--color-text-primary)",
                      display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }} title={risk.title}>
                      {risk.title}
                    </span>
                  </td>
                  <td style={{ padding: "var(--space-3)" }}>
                    <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)" }}>{risk.category}</span>
                  </td>
                  <td style={{ padding: "var(--space-3)" }}>
                    <Badge severity={risk.severity} />
                  </td>
                  <td style={{ padding: "var(--space-3)", fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
                    {risk.owner}
                  </td>
                  <td style={{ padding: "var(--space-3)" }}>
                    <span style={{
                      fontSize: "var(--text-sm)", fontFamily: "var(--font-mono)",
                      color: isOverdue(risk.dueDate) && risk.status !== "Closed" ? "var(--color-critical)" : "var(--color-text-secondary)",
                    }}>
                      {risk.dueDate}
                    </span>
                  </td>
                  <td style={{ padding: "var(--space-3)" }}>
                    <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>{risk.status}</span>
                  </td>
                  <td style={{ padding: "var(--space-2) var(--space-3)" }}>
                    <div style={{ display: "flex", gap: 2 }}>
                      <IconButton icon={<Eye size={14} />}   label="View"   onClick={() => onNavigate?.("risk_detail", risk.id)} />
                      <IconButton icon={<Edit2 size={14} />}  label="Edit"   onClick={() => onNavigate?.("risk_form", risk.id)} />
                      <IconButton icon={<Trash2 size={14} />} label="Delete" variant="danger" onClick={() => setDeleteId(risk.id)} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {sorted.length > 0 && (
        <div style={{
          padding: "var(--space-4) var(--space-6)",
          borderTop: "1px solid var(--color-border-subtle)",
          background: "var(--color-bg-surface)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          flexWrap: "wrap", gap: "var(--space-3)",
        }}>
          <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
            Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, sorted.length)} of {sorted.length}
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>Rows per page:</span>
              <select
                value={pageSize}
                onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
                style={{
                  background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)",
                  borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)",
                  fontSize: "var(--text-sm)", padding: "2px 6px", cursor: "pointer",
                }}
              >
                {PAGE_SIZE_OPTIONS.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
            <Button variant="secondary" size="sm" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
              <ArrowLeft size={13} /> Prev
            </Button>
            <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", minWidth: 60, textAlign: "center" }}>
              {page} / {totalPages}
            </span>
            <Button variant="secondary" size="sm" disabled={page === totalPages} onClick={() => setPage((p) => p + 1)}>
              Next <ArrowRight size={13} />
            </Button>
          </div>
        </div>
      )}

      {/* Delete confirm */}
      <ConfirmDialog
        open={!!deleteId}
        title="Delete risk"
        description={`Delete ${deleteId}? This action cannot be undone.`}
        confirmLabel="Delete risk"
        onConfirm={() => setDeleteId(null)}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  );
}
