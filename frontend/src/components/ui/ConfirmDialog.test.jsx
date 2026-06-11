import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { useState, useEffect } from "react";
import { ConfirmDialog } from "./index.jsx";

// Wrapper that re-renders (new onConfirm/onCancel references each time,
// like a real parent would produce) shortly after the dialog opens, to
// guard against the focus trap re-running on every parent re-render.
function Harness() {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setTimeout(() => setTick((t) => t + 1), 10);
    return () => clearTimeout(id);
  }, [tick]);

  return (
    <ConfirmDialog
      open
      title="Discard unsaved changes?"
      description="desc"
      confirmLabel="Discard changes"
      cancelLabel="Keep editing"
      onConfirm={() => {}}
      onCancel={() => {}}
    />
  );
}

describe("ConfirmDialog focus management (STORY-RISKFORM-003 NFR)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("focuses the first element on open and restores focus on close", async () => {
    const onCancel = vi.fn();
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();

    const { rerender } = render(
      <ConfirmDialog
        open
        title="Discard unsaved changes?"
        description="desc"
        confirmLabel="Discard changes"
        cancelLabel="Keep editing"
        onConfirm={() => {}}
        onCancel={onCancel}
      />
    );

    const dialog = await screen.findByRole("dialog");
    expect(dialog.contains(document.activeElement)).toBe(true);

    rerender(<></>);
    expect(document.activeElement).toBe(trigger);

    document.body.removeChild(trigger);
  });

  it("does not steal focus back to the first button when the parent re-renders while open", async () => {
    vi.useFakeTimers();
    render(<Harness />);

    const dialog = screen.getByRole("dialog");
    const buttons = dialog.querySelectorAll("button");
    const last = buttons[buttons.length - 1];

    act(() => {
      last.focus();
    });
    expect(document.activeElement).toBe(last);

    // Advance past the harness's scheduled re-render (new onConfirm/onCancel
    // closures). With a buggy [open, onCancel/onConfirm]-dependent focus
    // trap effect, this re-render re-runs the effect and yanks focus back to
    // the first focusable element — which would fail this assertion.
    await act(async () => {
      vi.advanceTimersByTime(15);
    });

    expect(document.activeElement).toBe(last);
  });
});
