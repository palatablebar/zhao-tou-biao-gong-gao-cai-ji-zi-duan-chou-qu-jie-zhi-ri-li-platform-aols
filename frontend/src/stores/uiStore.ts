/** UI 提示条 store（成功/失败反馈）。 */
type Listener = () => void;

export interface Toast {
  id: number;
  tone: 'ok' | 'warn' | 'error';
  text: string;
}

class UiStore {
  private toasts: Toast[] = [];
  private seq = 1;
  private listeners = new Set<Listener>();

  subscribe = (listener: Listener) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getToasts = () => this.toasts;

  push(tone: Toast['tone'], text: string) {
    const toast = { id: this.seq++, tone, text };
    this.toasts = [...this.toasts, toast];
    this.notify();
    window.setTimeout(() => this.dismiss(toast.id), 5200);
  }

  dismiss(id: number) {
    this.toasts = this.toasts.filter((toast) => toast.id !== id);
    this.notify();
  }

  private notify() {
    this.listeners.forEach((listener) => listener());
  }
}

export const uiStore = new UiStore();
