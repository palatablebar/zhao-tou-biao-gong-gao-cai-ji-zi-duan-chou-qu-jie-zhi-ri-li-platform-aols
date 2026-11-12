import { http } from './client';
import type { UserInfo } from '../types/models';

export interface LoginResult {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserInfo;
}

export const authApi = {
  login: (email: string, password: string) =>
    http.post<LoginResult>('/auth/login', { email, password }),
  me: () => http.get<{ user: UserInfo }>('/auth/me'),
};
