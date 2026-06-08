import { useState, useCallback } from "react";

let nextId = 0;

export function useToast() {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const add = useCallback((message, type = "info", options = {}) => {
    const id = ++nextId;
    setToasts((prev) => [...prev.slice(-2), { id, message, type, ...options }]);
    return id;
  }, []);

  const toast = {
    success: (msg, opts) => add(msg, "success", opts),
    error:   (msg, opts) => add(msg, "error",   { persistent: true, ...opts }),
    warning: (msg, opts) => add(msg, "warning", opts),
    info:    (msg, opts) => add(msg, "info",     opts),
  };

  return { toasts, dismiss, toast };
}
