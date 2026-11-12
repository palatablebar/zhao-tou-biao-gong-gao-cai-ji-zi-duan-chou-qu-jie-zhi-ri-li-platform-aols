import { useEffect, useRef } from 'react';

/** 固定间隔轮询（复核队列 / 日历刷新使用）；页面卸载自动清理。 */
export function usePolling(callback: () => void, intervalMs: number, enabled = true) {
  const saved = useRef(callback);
  saved.current = callback;

  useEffect(() => {
    if (!enabled) return undefined;
    const timer = window.setInterval(() => saved.current(), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs, enabled]);
}
