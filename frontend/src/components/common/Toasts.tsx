import { useSyncExternalStore } from 'react';
import { uiStore } from '../../stores/uiStore';

export default function Toasts() {
  const toasts = useSyncExternalStore(uiStore.subscribe, uiStore.getToasts);
  if (toasts.length === 0) return null;
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast-${toast.tone}`} onClick={() => uiStore.dismiss(toast.id)}>
          <span className="toast-mark">{toast.tone === 'ok' ? '✓' : toast.tone === 'warn' ? '!' : '×'}</span>
          <span>{toast.text}</span>
        </div>
      ))}
    </div>
  );
}
