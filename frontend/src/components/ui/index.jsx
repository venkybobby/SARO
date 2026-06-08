import React, { useState, useEffect, useRef, useCallback } from "react";
import { AlertCircle, Check, X, Info, AlertTriangle, CheckCircle } from "lucide-react";

/* ─── Badge ──────────────────────────────────────────────────────────────── */
const SEVERITY_MAP = {
  critical: { color: "var(--color-critical)", bg: "var(--color-critical-bg)", border: "var(--color-critical-border)", label: "Critical" },
  high:     { color: "var(--color-high)",     bg: "var(--color-high-bg)",     border: "var(--color-high-border)",     label: "High" },
  medium:   { color: "var(--color-medium)",   bg: "var(--color-medium-bg)",   border: "var(--color-medium-border)",   label: "Medium" },
  low:      { color: "var(--color-low)",       bg: "var(--color-low-bg)",      border: "var(--color-low-border)",      label: "Low" },
  info:     { color: "var(--color-info)",      bg: "var(--color-info-bg)",     border: "var(--color-info-border)",     label: "Info" },
  ai:       { color: "var(--color-ai)",        bg: "var(--color-ai-bg)",       border: "var(--color-ai-border)",       label: "AI" },
};

export function Badge({ severity, children, style }) {
  const s = SEVERITY_MAP[severity] || SEVERITY_MAP.info;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "2px 8px", borderRadius: 999,
      background: s.bg, border: `1px solid ${s.border}`,
      color: s.color, fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
      whiteSpace: "nowrap", fontFamily: "var(--font-display)",
      ...style,
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: "50%",
        background: s.color, flexShrink: 0,
      }} />
      {children || s.label}
    </span>
  );
}

/* ─── StatusDot ─────────────────────────────────────────────────────────── */
export function StatusDot({ status, pulse }) {
  const s = SEVERITY_MAP[status] || SEVERITY_MAP.info;
  return (
    <span style={{ position: "relative", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
      {pulse && (
        <span style={{
          position: "absolute", width: 8, height: 8, borderRadius: "50%",
          background: s.color, opacity: 0.5,
          animation: "pulse-ring 1.4s ease-out infinite",
        }} />
      )}
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: s.color, position: "relative" }} />
    </span>
  );
}

/* ─── Button ─────────────────────────────────────────────────────────────── */
const BTN_VARIANTS = {
  primary:   { bg: "var(--color-info)",     color: "var(--color-text-inverse)", border: "transparent",                   hover: "rgba(74,158,232,0.85)" },
  secondary: { bg: "var(--color-bg-overlay)", color: "var(--color-text-primary)", border: "var(--color-border-default)", hover: "var(--color-bg-elevated)" },
  ghost:     { bg: "transparent",           color: "var(--color-text-secondary)", border: "transparent",                 hover: "var(--color-bg-elevated)" },
  danger:    { bg: "var(--color-critical)", color: "#fff",                         border: "transparent",                 hover: "rgba(232,68,58,0.85)" },
};

const BTN_SIZES = {
  sm: { padding: "4px 10px", fontSize: "var(--text-sm)" },
  md: { padding: "7px 14px", fontSize: "var(--text-base)" },
  lg: { padding: "10px 20px", fontSize: "var(--text-md)" },
};

export function Button({ variant = "primary", size = "md", loading, disabled, children, onClick, type = "button", style, className }) {
  const v = BTN_VARIANTS[variant] || BTN_VARIANTS.primary;
  const sz = BTN_SIZES[size] || BTN_SIZES.md;
  const [hovered, setHovered] = useState(false);
  const isDisabled = disabled || loading;

  return (
    <button
      type={type}
      className={`btn ${className || ""}`}
      disabled={isDisabled}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        background: hovered && !isDisabled ? v.hover : v.bg,
        color: v.color,
        border: `1px solid ${v.border}`,
        borderRadius: "var(--radius-md)",
        fontWeight: "var(--weight-medium)",
        fontFamily: "var(--font-display)",
        cursor: isDisabled ? "not-allowed" : "pointer",
        opacity: isDisabled ? 0.6 : 1,
        transition: "background var(--transition-fast), opacity var(--transition-fast)",
        outline: "none",
        ...sz,
        ...style,
      }}
      onFocus={(e) => { e.currentTarget.style.boxShadow = "var(--focus-ring)"; }}
      onBlur={(e) => { e.currentTarget.style.boxShadow = "none"; }}
    >
      {loading && (
        <span style={{
          width: 12, height: 12, border: "2px solid currentColor",
          borderTopColor: "transparent", borderRadius: "50%",
          animation: "spin 0.7s linear infinite", flexShrink: 0,
        }} />
      )}
      {children}
    </button>
  );
}

/* ─── Input ──────────────────────────────────────────────────────────────── */
export function Input({ label, type = "text", value, onChange, onBlur, error, hint, required, autoFocus, autoComplete, placeholder, disabled, size = "md", id, name, style }) {
  const inputId = id || `input-${label?.toLowerCase().replace(/\s+/g, "-")}`;
  const errorId = `${inputId}-error`;
  const hintId  = `${inputId}-hint`;

  const describedBy = [error && errorId, hint && hintId].filter(Boolean).join(" ") || undefined;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, ...style }}>
      {label && (
        <label htmlFor={inputId} style={{
          fontSize: "var(--text-sm)", fontWeight: "var(--weight-medium)",
          color: "var(--color-text-secondary)", fontFamily: "var(--font-display)",
        }}>
          {label}
          {required && <span aria-label="required" style={{ color: "var(--color-critical)", marginLeft: 3 }}>*</span>}
        </label>
      )}
      <input
        id={inputId}
        name={name}
        type={type}
        value={value}
        onChange={onChange}
        onBlur={onBlur}
        required={required}
        autoFocus={autoFocus}
        autoComplete={autoComplete}
        placeholder={placeholder}
        disabled={disabled}
        aria-describedby={describedBy}
        aria-invalid={!!error}
        style={{
          background: "var(--color-bg-elevated)",
          border: `1px solid ${error ? "var(--color-critical)" : "var(--color-border-default)"}`,
          borderRadius: "var(--radius-md)",
          color: "var(--color-text-primary)",
          fontSize: size === "sm" ? "var(--text-sm)" : "var(--text-base)",
          padding: size === "sm" ? "6px 10px" : "8px 12px",
          outline: "none",
          width: "100%",
          transition: "border-color var(--transition-fast)",
          fontFamily: "var(--font-body)",
        }}
        onFocus={(e) => { e.target.style.borderColor = "var(--color-info)"; e.target.style.boxShadow = "var(--focus-ring)"; }}
        onBlur2={(e) => { e.target.style.borderColor = error ? "var(--color-critical)" : "var(--color-border-default)"; e.target.style.boxShadow = "none"; }}
      />
      {error && (
        <span id={errorId} role="alert" style={{
          display: "flex", alignItems: "center", gap: 4,
          fontSize: "var(--text-xs)", color: "var(--color-critical)",
        }}>
          <AlertCircle size={11} />
          {error}
        </span>
      )}
      {hint && !error && (
        <span id={hintId} style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
          {hint}
        </span>
      )}
    </div>
  );
}

/* ─── Skeleton ───────────────────────────────────────────────────────────── */
export function Skeleton({ width = "100%", height = 20, rounded }) {
  return (
    <span style={{
      display: "block",
      width, height,
      borderRadius: rounded ? 999 : "var(--radius-md)",
      background: "linear-gradient(90deg, var(--color-bg-elevated) 25%, var(--color-bg-overlay) 50%, var(--color-bg-elevated) 75%)",
      backgroundSize: "400px 100%",
      animation: "shimmer 1.4s ease-in-out infinite",
    }} />
  );
}

/* ─── EmptyState ─────────────────────────────────────────────────────────── */
export function EmptyState({ icon, title, description, action }) {
  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      padding: "var(--space-12) var(--space-8)", gap: "var(--space-3)",
      color: "var(--color-text-muted)", textAlign: "center",
    }}>
      {icon && (
        <span style={{ color: "var(--color-text-muted)", opacity: 0.6, marginBottom: "var(--space-2)" }}>
          {React.cloneElement(icon, { size: 40, strokeWidth: 1.5 })}
        </span>
      )}
      {title && (
        <p style={{ fontSize: "var(--text-md)", fontWeight: "var(--weight-semibold)", color: "var(--color-text-secondary)", fontFamily: "var(--font-display)" }}>
          {title}
        </p>
      )}
      {description && (
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)", maxWidth: 340 }}>
          {description}
        </p>
      )}
      {action && <div style={{ marginTop: "var(--space-3)" }}>{action}</div>}
    </div>
  );
}

/* ─── Toast ──────────────────────────────────────────────────────────────── */
const TOAST_ICONS = {
  success: <CheckCircle size={16} />,
  error:   <AlertCircle size={16} />,
  warning: <AlertTriangle size={16} />,
  info:    <Info size={16} />,
};

const TOAST_COLORS = {
  success: "var(--color-low)",
  error:   "var(--color-critical)",
  warning: "var(--color-medium)",
  info:    "var(--color-info)",
};

export function Toast({ message, type = "info", onDismiss, persistent }) {
  const [progress, setProgress] = useState(100);
  const duration = persistent ? null : 4000;

  useEffect(() => {
    if (!duration) return;
    const start = Date.now();
    const tick = setInterval(() => {
      const elapsed = Date.now() - start;
      const remaining = Math.max(0, 100 - (elapsed / duration) * 100);
      setProgress(remaining);
      if (remaining === 0) { clearInterval(tick); onDismiss?.(); }
    }, 50);
    return () => clearInterval(tick);
  }, [duration, onDismiss]);

  const color = TOAST_COLORS[type] || TOAST_COLORS.info;

  return (
    <div style={{
      background: "var(--color-bg-elevated)",
      border: `1px solid var(--color-border-default)`,
      borderLeft: `3px solid ${color}`,
      borderRadius: "var(--radius-lg)",
      padding: "var(--space-3) var(--space-4)",
      boxShadow: "var(--shadow-md)",
      minWidth: 280, maxWidth: 380,
      position: "relative", overflow: "hidden",
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: "var(--space-2)" }}>
        <span style={{ color, flexShrink: 0, marginTop: 1 }}>{TOAST_ICONS[type]}</span>
        <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-primary)", flex: 1, lineHeight: 1.4 }}>
          {message}
        </span>
        <button onClick={onDismiss} style={{
          background: "none", border: "none", cursor: "pointer",
          color: "var(--color-text-muted)", padding: 2, flexShrink: 0,
        }}>
          <X size={14} />
        </button>
      </div>
      {!persistent && (
        <div style={{
          position: "absolute", bottom: 0, left: 0, height: 2,
          width: `${progress}%`, background: color,
          transition: "width 50ms linear",
        }} />
      )}
    </div>
  );
}

/* ─── ToastContainer ─────────────────────────────────────────────────────── */
export function ToastContainer({ toasts, onDismiss }) {
  return (
    <div
      aria-live="polite"
      style={{
        position: "fixed", bottom: "var(--space-6)", right: "var(--space-6)",
        display: "flex", flexDirection: "column", gap: "var(--space-2)",
        zIndex: "var(--z-toast)", pointerEvents: "none",
      }}
    >
      {toasts.slice(-3).map((t) => (
        <div key={t.id} style={{ pointerEvents: "auto" }}>
          <Toast
            message={t.message}
            type={t.type}
            persistent={t.persistent}
            onDismiss={() => onDismiss(t.id)}
          />
        </div>
      ))}
    </div>
  );
}

/* ─── ConfirmDialog ──────────────────────────────────────────────────────── */
export function ConfirmDialog({ open, title, description, confirmLabel = "Confirm", onConfirm, onCancel, requireTyping }) {
  const [typed, setTyped] = useState("");
  const canConfirm = !requireTyping || typed === requireTyping;

  useEffect(() => {
    if (!open) setTyped("");
    const handler = (e) => { if (e.key === "Escape") onCancel?.(); };
    if (open) document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
      aria-describedby="confirm-desc"
      style={{
        position: "fixed", inset: 0,
        zIndex: "var(--z-modal)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
    >
      <div
        style={{
          position: "absolute", inset: 0,
          background: "rgba(0,0,0,0.7)", backdropFilter: "blur(2px)",
          zIndex: "var(--z-modal-backdrop)",
        }}
        onClick={onCancel}
      />
      <div style={{
        position: "relative", zIndex: "var(--z-modal)",
        background: "var(--color-bg-elevated)",
        border: "1px solid var(--color-border-default)",
        borderRadius: "var(--radius-xl)",
        padding: "var(--space-8)",
        width: 420, maxWidth: "calc(100vw - 32px)",
        boxShadow: "var(--shadow-lg)",
      }}>
        <h2 id="confirm-title" style={{
          fontSize: "var(--text-md)", fontWeight: "var(--weight-semibold)",
          color: "var(--color-text-primary)", fontFamily: "var(--font-display)",
          marginBottom: "var(--space-2)",
        }}>
          {title}
        </h2>
        <p id="confirm-desc" style={{
          fontSize: "var(--text-sm)", color: "var(--color-text-secondary)",
          lineHeight: 1.6, marginBottom: requireTyping ? "var(--space-4)" : "var(--space-6)",
        }}>
          {description}
        </p>
        {requireTyping && (
          <div style={{ marginBottom: "var(--space-6)" }}>
            <Input
              label={`Type "${requireTyping}" to confirm`}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoFocus
            />
          </div>
        )}
        <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end" }}>
          <Button variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button variant="danger" disabled={!canConfirm} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}

/* ─── AIBadge ─────────────────────────────────────────────────────────────── */
export function AIBadge() {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "2px 7px", borderRadius: 999,
      background: "var(--color-ai-bg)",
      border: "1px solid var(--color-ai-border)",
      color: "var(--color-ai)",
      fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
      fontFamily: "var(--font-display)",
    }}>
      ✦ AI
    </span>
  );
}

/* ─── PageHeader ─────────────────────────────────────────────────────────── */
export function PageHeader({ title, subtitle, breadcrumb, actions }) {
  return (
    <header style={{
      padding: "var(--space-5) var(--space-6)",
      borderBottom: "1px solid var(--color-border-subtle)",
      background: "var(--color-bg-surface)",
      display: "flex", alignItems: "flex-start", justifyContent: "space-between",
      gap: "var(--space-4)", flexWrap: "wrap",
    }}>
      <div>
        {breadcrumb && (
          <nav aria-label="Breadcrumb" style={{
            display: "flex", alignItems: "center", gap: 6,
            fontSize: "var(--text-xs)", color: "var(--color-text-muted)",
            marginBottom: "var(--space-1)", fontFamily: "var(--font-body)",
          }}>
            {breadcrumb}
          </nav>
        )}
        <h1 style={{
          fontSize: "var(--text-xl)", fontWeight: "var(--weight-semibold)",
          color: "var(--color-text-primary)", fontFamily: "var(--font-display)",
          lineHeight: 1.2,
        }}>
          {title}
        </h1>
        {subtitle && (
          <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", marginTop: 3 }}>
            {subtitle}
          </p>
        )}
      </div>
      {actions && (
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexShrink: 0 }}>
          {actions}
        </div>
      )}
    </header>
  );
}

/* ─── IconButton ─────────────────────────────────────────────────────────── */
export function IconButton({ icon, label, onClick, variant = "ghost", disabled }) {
  const [hovered, setHovered] = useState(false);
  const isGhost = variant === "ghost";
  const isDanger = variant === "danger";

  return (
    <button
      className="icon-btn"
      title={label}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        padding: "var(--space-2)", borderRadius: "var(--radius-md)",
        background: hovered ? (isDanger ? "var(--color-critical-bg)" : "var(--color-bg-overlay)") : "transparent",
        border: "none",
        color: isDanger ? (hovered ? "var(--color-critical)" : "var(--color-text-muted)") : "var(--color-text-muted)",
        cursor: "pointer",
        transition: "background var(--transition-fast), color var(--transition-fast)",
        outline: "none",
      }}
      onFocus={(e) => { e.currentTarget.style.boxShadow = "var(--focus-ring)"; }}
      onBlur={(e) => { e.currentTarget.style.boxShadow = "none"; }}
    >
      {icon}
    </button>
  );
}
