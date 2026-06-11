import { useCallback, useRef, useState } from "react";

/**
 * Shared "unsaved changes" navigation guard (STORY-RISKFORM-003, AC-2).
 *
 * A page (e.g. RiskForm) registers a `() => boolean` guard reflecting its
 * dirty state via `registerDirtyGuard`. `handleNavigate` is then used as the
 * single navigation entry point (Sidebar clicks, breadcrumbs, etc.) — if the
 * registered guard reports dirty, navigation is deferred and `pendingNav` is
 * set so the caller can show a confirmation dialog.
 */
export function useDirtyNavGuard(navigate) {
  const dirtyGuardRef = useRef(null);
  const [pendingNav, setPendingNav] = useState(null);

  const registerDirtyGuard = useCallback((fn) => {
    dirtyGuardRef.current = fn;
  }, []);

  const handleNavigate = useCallback((page, payload) => {
    if (dirtyGuardRef.current?.()) {
      setPendingNav({ page, payload });
      return;
    }
    navigate(page, payload);
  }, [navigate]);

  const confirmNav = useCallback(() => {
    setPendingNav((nav) => {
      if (nav) {
        dirtyGuardRef.current = null;
        navigate(nav.page, nav.payload);
      }
      return null;
    });
  }, [navigate]);

  const cancelNav = useCallback(() => setPendingNav(null), []);

  return { pendingNav, registerDirtyGuard, handleNavigate, confirmNav, cancelNav };
}
