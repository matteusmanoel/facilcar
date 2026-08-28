"use client";

import { useEffect } from "react";

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return target.isContentEditable;
}

/** Clears multi-select when Escape is pressed outside a text field. */
export function useClearSelectionOnEscape(onClear: () => void, enabled = true) {
  useEffect(() => {
    if (!enabled) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      if (isTypingTarget(event.target)) return;
      event.preventDefault();
      onClear();
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClear, enabled]);
}
