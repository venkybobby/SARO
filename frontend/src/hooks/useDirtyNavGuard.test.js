import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDirtyNavGuard } from "./useDirtyNavGuard";

describe("useDirtyNavGuard (STORY-RISKFORM-003 AC-2)", () => {
  it("navigates immediately when no dirty guard is registered", () => {
    const navigate = vi.fn();
    const { result } = renderHook(() => useDirtyNavGuard(navigate));

    act(() => result.current.handleNavigate("risk_register"));

    expect(navigate).toHaveBeenCalledWith("risk_register", undefined);
    expect(result.current.pendingNav).toBeNull();
  });

  it("defers navigation and exposes pendingNav when the registered guard reports dirty", () => {
    const navigate = vi.fn();
    const { result } = renderHook(() => useDirtyNavGuard(navigate));

    act(() => result.current.registerDirtyGuard(() => true));
    act(() => result.current.handleNavigate("dashboard", "p1"));

    expect(navigate).not.toHaveBeenCalled();
    expect(result.current.pendingNav).toEqual({ page: "dashboard", payload: "p1" });
  });

  it("confirmNav navigates, clears pendingNav, and clears the guard so subsequent navigation proceeds", () => {
    const navigate = vi.fn();
    const { result } = renderHook(() => useDirtyNavGuard(navigate));

    act(() => result.current.registerDirtyGuard(() => true));
    act(() => result.current.handleNavigate("dashboard"));
    act(() => result.current.confirmNav());

    expect(navigate).toHaveBeenCalledWith("dashboard", undefined);
    expect(result.current.pendingNav).toBeNull();

    act(() => result.current.handleNavigate("risk_register"));
    expect(navigate).toHaveBeenCalledWith("risk_register", undefined);
    expect(result.current.pendingNav).toBeNull();
  });

  it("cancelNav clears pendingNav without navigating, and the guard remains active", () => {
    const navigate = vi.fn();
    const { result } = renderHook(() => useDirtyNavGuard(navigate));

    act(() => result.current.registerDirtyGuard(() => true));
    act(() => result.current.handleNavigate("dashboard"));
    act(() => result.current.cancelNav());

    expect(navigate).not.toHaveBeenCalled();
    expect(result.current.pendingNav).toBeNull();

    act(() => result.current.handleNavigate("risk_register"));
    expect(navigate).not.toHaveBeenCalled();
    expect(result.current.pendingNav).toEqual({ page: "risk_register", payload: undefined });
  });

  it("a guard that reports clean (registerDirtyGuard(null)) lets navigation proceed", () => {
    const navigate = vi.fn();
    const { result } = renderHook(() => useDirtyNavGuard(navigate));

    act(() => result.current.registerDirtyGuard(() => true));
    act(() => result.current.registerDirtyGuard(null));
    act(() => result.current.handleNavigate("dashboard"));

    expect(navigate).toHaveBeenCalledWith("dashboard", undefined);
    expect(result.current.pendingNav).toBeNull();
  });
});
