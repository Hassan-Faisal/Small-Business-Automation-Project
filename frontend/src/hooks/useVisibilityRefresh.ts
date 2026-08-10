import { useEffect, useRef } from "react";

export const PAGE_REFRESH_INTERVAL_MS = 20_000;

type RefreshCallback = () => Promise<void> | void;

export function useVisibilityRefresh(refresh: RefreshCallback, enabled = true): void {
  const refreshRef = useRef(refresh);
  const inFlightRef = useRef(false);

  useEffect(() => {
    refreshRef.current = refresh;
  }, [refresh]);

  useEffect(() => {
    if (!enabled) return undefined;

    const runRefresh = () => {
      if (document.visibilityState !== "visible" || inFlightRef.current) return;
      inFlightRef.current = true;
      Promise.resolve(refreshRef.current()).finally(() => {
        inFlightRef.current = false;
      });
    };
    const interval = window.setInterval(runRefresh, PAGE_REFRESH_INTERVAL_MS);
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") runRefresh();
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [enabled]);
}
