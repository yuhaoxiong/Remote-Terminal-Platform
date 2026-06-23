import axios, { AxiosHeaders, type AxiosError, type InternalAxiosRequestConfig } from "axios";

const ACCESS_TOKEN_KEY = "edge-platform-access-token";
const REFRESH_TOKEN_KEY = "edge-platform-refresh-token";
export const AUTH_EXPIRED_EVENT = "edge-platform-auth-expired";

type AuthRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
  skipAuthRefresh?: boolean;
};

const api = axios.create({
  baseURL: "/api",
});

api.interceptors.request.use((config) => {
  const token = window.localStorage.getItem(ACCESS_TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshPromise: Promise<TokenResponse> | null = null;

function getRefreshToken(): string | null {
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

function isAuthEndpoint(url: string | undefined): boolean {
  return Boolean(url?.includes("/auth/login") || url?.includes("/auth/refresh"));
}

function notifyAuthExpired() {
  clearAuthTokens();
  window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const status = error.response?.status;
    const originalRequest = error.config as AuthRequestConfig | undefined;
    if (
      status !== 401 ||
      !originalRequest ||
      originalRequest._retry ||
      originalRequest.skipAuthRefresh ||
      isAuthEndpoint(originalRequest.url)
    ) {
      throw error;
    }

    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      notifyAuthExpired();
      throw error;
    }

    originalRequest._retry = true;
    try {
      refreshPromise ??= api
        .post<TokenResponse>(
          "/auth/refresh",
          { refresh_token: refreshToken },
          { skipAuthRefresh: true } as AuthRequestConfig,
        )
        .then((response) => response.data)
        .finally(() => {
          refreshPromise = null;
        });
      const token = await refreshPromise;
      setAuthTokens(token.access_token, token.refresh_token);
      originalRequest.headers = AxiosHeaders.from(originalRequest.headers);
      originalRequest.headers.set("Authorization", `Bearer ${token.access_token}`);
      return api(originalRequest);
    } catch (refreshError) {
      notifyAuthExpired();
      throw refreshError;
    }
  },
);


export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface PasswordChangeRequest {

export function hasStoredAccessToken(): boolean {
  return Boolean(window.localStorage.getItem(ACCESS_TOKEN_KEY));
}

export function getAccessToken(): string | null {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setAuthTokens(accessToken: string, refreshToken: string) {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearAuthTokens() {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}


export function buildApiWebSocketUrl(path: string, token: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const separator = path.includes("?") ? "&" : "?";
  return `${protocol}//${window.location.host}${path}${separator}token=${encodeURIComponent(token)}`;
}

