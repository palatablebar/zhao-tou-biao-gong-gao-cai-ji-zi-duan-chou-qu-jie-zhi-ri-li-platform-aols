/** 极简外部 store：JWT + 当前用户（useSyncExternalStore 订阅）。 */
import type { UserInfo } from '../types/models';
import { authApi } from '../api/auth';

const TOKEN_KEY = 'bidsift.token';
const USER_KEY = 'bidsift.user';

export interface AuthState {
  token: string | null;
  user: UserInfo | null;
  bootstrapped: boolean;
}

type Listener = () => void;

class AuthStore {
  private state: AuthState = { token: null, user: null, bootstrapped: false };
  private listeners = new Set<Listener>();

  subscribe = (listener: Listener) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getState = (): AuthState => this.state;

  getToken = (): string | null => this.state.token;

  private emit(next: Partial<AuthState>) {
    this.state = { ...this.state, ...next };
    this.listeners.forEach((listener) => listener());
  }

  async bootstrap() {
    if (this.state.bootstrapped) return;
    const token = localStorage.getItem(TOKEN_KEY);
    const rawUser = localStorage.getItem(USER_KEY);
    let user: UserInfo | null = null;
    if (rawUser) {
      try {
        user = JSON.parse(rawUser) as UserInfo;
      } catch {
        user = null;
      }
    }
    this.emit({ token, user, bootstrapped: true });
    if (token) {
      try {
        const result = await authApi.me();
        this.setSession(token, result.user);
      } catch {
        this.logout();
      }
    }
  }

  setSession(token: string, user: UserInfo) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    this.emit({ token, user, bootstrapped: true });
  }

  logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    this.emit({ token: null, user: null, bootstrapped: true });
  }
}

export const authStore = new AuthStore();
