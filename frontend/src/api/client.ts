import { authStore } from '../stores/authStore';

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(status: number, payload: unknown) {
    super('api-error');
    this.status = status;
    this.payload = payload;
  }
}

const BASE = '/api';

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = authStore.getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${BASE}${path}`, { ...init, headers });
  if (response.status === 401) {
    authStore.logout();
  }
  const text = await response.text();
  const data = text ? safeParse(text) : null;
  if (!response.ok) {
    throw new ApiError(response.status, data);
  }
  return data as T;
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export const http = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'POST',
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'PATCH',
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
};

/** 下载 CSV：带 Bearer 头，用 blob 触发浏览器保存，用于导出本周必投名单。 */
export async function downloadFile(path: string, fallbackName: string): Promise<string> {
  const token = authStore.getToken();
  const response = await fetch(`${BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(response.status, safeParse(text));
  }
  const disposition = response.headers.get('content-disposition') || '';
  const match = disposition.match(/filename="?([^";]+)"?/);
  const filename = match ? match[1] : fallbackName;
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return filename;
}
