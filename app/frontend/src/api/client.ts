import type { ApiErrorBody } from './types';

const DEFAULT_BASE_URL = 'http://localhost:8000';

/**
 * Reads from Expo's EXPO_PUBLIC_ env var convention -- readable directly
 * via process.env in app code, no extra package (e.g. expo-constants)
 * required. See `.env.example` for how to point this at your backend.
 */
export const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? DEFAULT_BASE_URL;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init.headers },
    });
  } catch {
    // Covers the backend being unreachable entirely (wrong URL, server
    // not running, no network) -- distinct from a request that reached
    // the server but failed, which is handled below.
    throw new ApiError(
      0,
      'network_error',
      'Could not reach the server. Check your connection and that the backend is running.'
    );
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as Partial<ApiErrorBody> | null;
    throw new ApiError(response.status, body?.error ?? 'unknown_error', body?.detail ?? 'Something went wrong.');
  }

  return (await response.json()) as T;
}

export const apiClient = {
  get: <T>(path: string): Promise<T> => request<T>(path),
  post: <T>(path: string, body: unknown): Promise<T> =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
};
