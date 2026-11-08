import * as Keychain from 'react-native-keychain';

import { API_BASE_URL } from '../config';

const SESSION_SERVICE = 'com.concertrip.session';

type TokenResponse = {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
};

export type AuthUser = {
  id: string;
  email: string;
  isVerified: boolean;
};

export type RegisterResponse = {
  user: AuthUser;
  message: string;
  verificationToken?: string | null;
};

async function storeTokens(tokens: TokenResponse) {
  await Keychain.setGenericPassword('session', JSON.stringify(tokens), {
    service: SESSION_SERVICE,
  });
}

async function readTokens(): Promise<TokenResponse | null> {
  const credentials = await Keychain.getGenericPassword({ service: SESSION_SERVICE });
  if (!credentials) return null;
  return JSON.parse(credentials.password) as TokenResponse;
}

async function clearTokens() {
  await Keychain.resetGenericPassword({ service: SESSION_SERVICE });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function register(email: string, password: string) {
  return request<RegisterResponse>('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function verifyEmail(token: string) {
  return request<AuthUser>('/api/v1/auth/verify-email', {
    method: 'POST',
    body: JSON.stringify({ token }),
  });
}

export async function login(email: string, password: string) {
  const tokens = await request<TokenResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password, device_name: 'mobile' }),
  });
  await storeTokens(tokens);
  return tokens;
}

export async function refreshSession() {
  const tokens = await readTokens();
  if (!tokens) return null;
  try {
    const nextTokens = await request<TokenResponse>('/api/v1/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: tokens.refreshToken }),
    });
    await storeTokens(nextTokens);
    return nextTokens;
  } catch {
    await clearTokens();
    return null;
  }
}

export async function authenticatedRequest<T>(path: string, init?: RequestInit) {
  let tokens = await readTokens();
  if (!tokens) throw new Error('Not authenticated');

  const send = (accessToken: string) =>
    fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
        Authorization: `Bearer ${accessToken}`,
      },
    });

  let response = await send(tokens.accessToken);
  if (response.status === 401) {
    tokens = await refreshSession();
    if (!tokens) throw new Error('Session expired');
    response = await send(tokens.accessToken);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function currentUser() {
  return authenticatedRequest<AuthUser>('/api/v1/auth/me');
}

export async function logout() {
  const tokens = await readTokens();
  if (tokens) {
    await request('/api/v1/auth/logout', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: tokens.refreshToken }),
    }).catch(() => undefined);
  }
  await clearTokens();
}
